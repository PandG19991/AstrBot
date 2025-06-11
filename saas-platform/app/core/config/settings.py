"""
应用配置设置

使用Pydantic Settings管理应用配置，支持环境变量。
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        frozen=True,  # 使配置不可变
    )
    
    # 基本应用配置
    PROJECT_NAME: str = "AstrBot SaaS Platform"
    APP_NAME: str = "AstrBot SaaS Platform"  # 兼容测试用的别名
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # 服务器配置 - 支持多种环境变量名
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    # 安全配置
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 修复为合理的30分钟
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30天
    
    # JWT配置
    ALGORITHM: str = "HS256"
    
    # CORS配置
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://localhost:3000",
        "https://localhost:8000",
    ]
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """处理CORS origins配置"""
        # 检查环境变量CORS_ALLOWED_ORIGINS作为别名
        import os
        cors_env_value = os.environ.get('CORS_ALLOWED_ORIGINS')
        if cors_env_value:
            v = cors_env_value
        
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    # 数据库配置 - 支持多种环境变量名
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "astrbot_saas"
    POSTGRES_PORT: int = 5432
    
    DATABASE_URL: Optional[str] = None
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        """组装数据库连接URL"""
        if isinstance(v, str):
            return v
        
        user = values.get('POSTGRES_USER')
        password = values.get('POSTGRES_PASSWORD')
        host = values.get('POSTGRES_SERVER')
        port = values.get('POSTGRES_PORT')
        db = values.get('POSTGRES_DB')
        
        # 处理空密码的情况
        if password:
            return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
        else:
            return f"postgresql+asyncpg://{user}@{host}:{port}/{db}"
    
    # Redis配置 - 支持环境变量
    REDIS_URL: str = "redis://localhost:6379/0"
    
    @validator("REDIS_URL", pre=True)
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        """组装Redis连接URL"""
        if isinstance(v, str) and v != "redis://localhost:6379/0":
            return v  # 如果已经是完整URL就直接使用
        
        # 从环境变量获取Redis配置
        import os
        redis_host = os.environ.get('REDIS_HOST', 'localhost')
        redis_port = os.environ.get('REDIS_PORT', '6379')
        redis_password = os.environ.get('REDIS_PASSWORD', '')
        redis_db = os.environ.get('REDIS_DB', '0')
        
        # 组装Redis URL
        if redis_password:
            return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            return f"redis://{redis_host}:{redis_port}/{redis_db}"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            return "INFO"  # 回退到默认值
        return v.upper()
    
    # 邮件配置
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: Optional[str] = None
    
    # 超级用户配置
    FIRST_SUPERUSER: str = "admin@astrbot.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin123"
    
    # 环境配置
    ENVIRONMENT: str = "development"
    
    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.ENVIRONMENT == "production"
    
    # 兼容性别名属性 - 用于向后兼容和测试
    @property
    def HOST(self) -> str:
        """服务器主机地址别名"""
        return self.SERVER_HOST
    
    @property 
    def PORT(self) -> int:
        """服务器端口别名"""
        return self.SERVER_PORT
    
    @property
    def DB_HOST(self) -> str:
        """数据库主机别名"""
        return self.POSTGRES_SERVER
    
    @property
    def DB_USER(self) -> str:
        """数据库用户别名"""
        return self.POSTGRES_USER
    
    @property
    def DB_PASSWORD(self) -> str:
        """数据库密码别名"""
        return self.POSTGRES_PASSWORD
    
    @property
    def DB_NAME(self) -> str:
        """数据库名称别名"""
        return self.POSTGRES_DB
    
    @property
    def DB_PORT(self) -> int:
        """数据库端口别名"""
        return self.POSTGRES_PORT
    
    @property
    def CORS_ALLOWED_ORIGINS(self) -> List[str]:
        """CORS允许源别名"""
        return self.BACKEND_CORS_ORIGINS
    
    # 多租户配置
    MAX_TENANTS_PER_USER: int = 3
    DEFAULT_TENANT_QUOTA: Dict[str, int] = {
        "max_sessions": 1000,
        "max_messages_per_month": 10000,
        "max_agents": 10,
    }
    
    # 外部服务配置
    WEBHOOK_BASE_URL: str = "https://api.astrbot.com"
    ASTRBOT_API_TIMEOUT: int = 30
    
    # 文件存储配置
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    # 添加环境变量别名支持
    def __init__(self, **kwargs):
        """初始化设置，支持环境变量别名"""
        # 处理环境变量别名映射
        env_aliases = {
            'HOST': 'SERVER_HOST',
            'PORT': 'SERVER_PORT',
            'DB_HOST': 'POSTGRES_SERVER',
            'DB_USER': 'POSTGRES_USER',
            'DB_PASSWORD': 'POSTGRES_PASSWORD',
            'DB_NAME': 'POSTGRES_DB',
            'DB_PORT': 'POSTGRES_PORT',
        }
        
        # 处理来自环境变量的别名
        import os
        for alias, actual_field in env_aliases.items():
            if alias in os.environ and actual_field not in kwargs:
                # 将环境变量别名映射到实际字段
                env_value = os.environ[alias]
                # 类型转换
                if actual_field in ['SERVER_PORT', 'POSTGRES_PORT']:
                    kwargs[actual_field] = int(env_value)
                elif actual_field == 'DEBUG':
                    kwargs[actual_field] = env_value.lower() in ('true', '1', 'yes', 'on')
                else:
                    kwargs[actual_field] = env_value
        
        super().__init__(**kwargs)

    def __str__(self) -> str:
        """字符串表示，隐藏敏感信息"""
        # 获取所有字段，但排除敏感信息
        sensitive_fields = {
            'SECRET_KEY', 'POSTGRES_PASSWORD', 'SMTP_PASSWORD', 
            'FIRST_SUPERUSER_PASSWORD'
        }
        
        field_strs = []
        for field_name in self.model_fields:
            if field_name not in sensitive_fields:
                value = getattr(self, field_name)
                # 对于可能包含密码的URL也要隐藏
                if field_name in ['DATABASE_URL', 'REDIS_URL'] and isinstance(value, str):
                    # 隐藏URL中的密码部分
                    if ':' in value and '@' in value:
                        # 模式：scheme://user:password@host:port/db
                        parts = value.split('@')
                        if len(parts) == 2:
                            scheme_user_pass, host_port_db = parts
                            if ':' in scheme_user_pass:
                                scheme_user, _ = scheme_user_pass.rsplit(':', 1)
                                value = f"{scheme_user}:***@{host_port_db}"
                field_strs.append(f"{field_name}={repr(value)}")
        
        return " ".join(field_strs)


# 创建全局设置实例
settings = Settings()


def get_settings() -> Settings:
    """
    获取应用设置实例
    
    这是一个依赖注入函数，用于在FastAPI中获取配置设置
    
    Returns:
        Settings: 全局设置实例
    """
    return settings 