"""
日志记录工具模块

提供结构化日志记录功能，支持多租户环境的日志管理。
"""

import logging
import sys
from typing import Any, Dict, Optional
from datetime import datetime
import json

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为结构化JSON格式"""
        
        # 基础日志信息
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, 'tenant_id'):
            log_data["tenant_id"] = record.tenant_id
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'session_id'):
            log_data["session_id"] = record.session_id
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """设置应用日志配置"""
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # 设置格式化器
    if settings.is_development:
        # 开发环境使用简单格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:
        # 生产环境使用结构化格式
        formatter = StructuredFormatter()
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


class ContextLogger:
    """带上下文的日志记录器"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs) -> None:
        """设置日志上下文"""
        self.context.update(kwargs)
    
    def clear_context(self) -> None:
        """清除日志上下文"""
        self.context.clear()
    
    def _log(self, level: int, message: str, **kwargs) -> None:
        """内部日志记录方法"""
        extra_data = {**self.context, **kwargs}
        
        # 创建LogRecord并添加额外字段
        record = self.logger.makeRecord(
            self.logger.name, level, "", 0, message, (), None
        )
        
        # 添加上下文数据
        for key, value in extra_data.items():
            setattr(record, key, value)
        
        self.logger.handle(record)
    
    def debug(self, message: str, **kwargs) -> None:
        """记录调试信息"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """记录信息"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """记录警告"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """记录错误"""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """记录严重错误"""
        self._log(logging.CRITICAL, message, **kwargs)


# 全局日志记录器缓存
_loggers: Dict[str, ContextLogger] = {}


def get_logger(name: str) -> ContextLogger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
        
    Returns:
        ContextLogger: 带上下文的日志记录器实例
    """
    if name not in _loggers:
        _loggers[name] = ContextLogger(name)
    
    return _loggers[name]


# 初始化日志配置
setup_logging() 