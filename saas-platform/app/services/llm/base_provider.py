"""
LLM提供商抽象基类

定义所有LLM提供商必须实现的统一接口
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from app.schemas.message import MessageRead


@dataclass
class LLMMessage:
    """LLM消息格式"""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    """LLM响应格式"""
    content: str
    finish_reason: str  # "stop", "length", "function_call", etc.
    usage: Optional[Dict[str, int]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMConfig:
    """LLM配置信息"""
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: Optional[List[str]] = None
    custom_params: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """LLM提供商抽象基类"""
    
    def __init__(self, config: LLMConfig, api_key: str, **kwargs):
        """
        初始化LLM提供商
        
        Args:
            config: LLM配置
            api_key: API密钥
            **kwargs: 其他自定义参数
        """
        self.config = config
        self.api_key = api_key
        self.custom_params = kwargs
        
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称"""
        pass
    
    @property
    @abstractmethod
    def supported_models(self) -> List[str]:
        """支持的模型列表"""
        pass
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[LLMMessage],
        config_override: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """
        生成聊天响应
        
        Args:
            messages: 消息历史
            config_override: 临时配置覆盖
            
        Returns:
            LLMResponse: 生成的响应
            
        Raises:
            LLMProviderError: 调用失败
        """
        pass
    
    @abstractmethod
    async def generate_stream_response(
        self, 
        messages: List[LLMMessage],
        config_override: Optional[LLMConfig] = None
    ) -> AsyncIterator[str]:
        """
        生成流式聊天响应
        
        Args:
            messages: 消息历史
            config_override: 临时配置覆盖
            
        Yields:
            str: 响应内容片段
            
        Raises:
            LLMProviderError: 调用失败
        """
        pass
    
    @abstractmethod
    async def validate_config(self) -> bool:
        """
        验证配置有效性
        
        Returns:
            bool: 配置是否有效
        """
        pass
    
    @abstractmethod
    async def get_token_count(self, text: str) -> int:
        """
        计算文本的token数量
        
        Args:
            text: 输入文本
            
        Returns:
            int: token数量
        """
        pass
    
    def messages_from_session_history(
        self, 
        session_messages: List[MessageRead],
        system_prompt: Optional[str] = None
    ) -> List[LLMMessage]:
        """
        从会话消息历史构建LLM消息列表
        
        Args:
            session_messages: 会话消息历史
            system_prompt: 系统提示词
            
        Returns:
            List[LLMMessage]: LLM消息列表
        """
        llm_messages = []
        
        # 添加系统提示词
        if system_prompt:
            llm_messages.append(LLMMessage(
                role="system",
                content=system_prompt
            ))
        
        # 转换会话消息
        for msg in session_messages:
            role = "user" if msg.message_type == "user" else "assistant"
            llm_messages.append(LLMMessage(
                role=role,
                content=msg.content,
                metadata={
                    "message_id": str(msg.id),
                    "session_id": str(msg.session_id),
                    "created_at": msg.created_at.isoformat()
                }
            ))
        
        return llm_messages
    
    def estimate_context_tokens(self, messages: List[LLMMessage]) -> int:
        """
        估算消息列表的总token数
        
        Args:
            messages: LLM消息列表
            
        Returns:
            int: 估算的token数量
        """
        # 简单估算：每个字符约0.75个token（中文约1个token）
        total_chars = sum(len(msg.content) for msg in messages)
        return int(total_chars * 0.8)  # 保守估算
    
    def truncate_messages_by_tokens(
        self, 
        messages: List[LLMMessage], 
        max_tokens: int,
        keep_system: bool = True
    ) -> List[LLMMessage]:
        """
        按token限制截断消息列表
        
        Args:
            messages: 原始消息列表
            max_tokens: 最大token数
            keep_system: 是否保留系统消息
            
        Returns:
            List[LLMMessage]: 截断后的消息列表
        """
        if not messages:
            return []
        
        # 分离系统消息和对话消息
        system_messages = [msg for msg in messages if msg.role == "system"]
        conversation_messages = [msg for msg in messages if msg.role != "system"]
        
        result = []
        current_tokens = 0
        
        # 优先保留系统消息
        if keep_system and system_messages:
            for msg in system_messages:
                msg_tokens = self.estimate_context_tokens([msg])
                if current_tokens + msg_tokens <= max_tokens:
                    result.append(msg)
                    current_tokens += msg_tokens
        
        # 从最新消息开始添加对话消息
        for msg in reversed(conversation_messages):
            msg_tokens = self.estimate_context_tokens([msg])
            if current_tokens + msg_tokens <= max_tokens:
                result.insert(-len(system_messages) if keep_system else 0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        return result


class LLMProviderError(Exception):
    """LLM提供商异常"""
    
    def __init__(self, message: str, provider: str, error_code: Optional[str] = None):
        self.provider = provider
        self.error_code = error_code
        super().__init__(f"[{provider}] {message}")


class LLMRateLimitError(LLMProviderError):
    """LLM调用频率限制异常"""
    pass


class LLMQuotaExceededError(LLMProviderError):
    """LLM配额超限异常"""
    pass


class LLMInvalidRequestError(LLMProviderError):
    """LLM请求参数无效异常"""
    pass 