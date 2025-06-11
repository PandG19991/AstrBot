"""
Dify LLM提供商实现

集成Dify平台的API调用
"""
import asyncio
import json
import logging
from typing import List, Optional, AsyncIterator, Dict, Any

import httpx
from httpx import AsyncClient, ConnectTimeout, ReadTimeout

from .base_provider import (
    BaseLLMProvider, 
    LLMMessage, 
    LLMResponse, 
    LLMConfig,
    LLMProviderError,
    LLMRateLimitError,
    LLMQuotaExceededError,
    LLMInvalidRequestError
)

# 配置日志
logger = logging.getLogger(__name__)


class DifyProvider(BaseLLMProvider):
    """Dify LLM提供商实现"""
    
    def __init__(
        self, 
        config: LLMConfig, 
        api_key: str, 
        base_url: str = "https://api.dify.ai/v1",
        timeout: int = 30,
        **kwargs
    ):
        """
        初始化Dify提供商
        
        Args:
            config: LLM配置
            api_key: Dify API密钥
            base_url: Dify API基础URL
            timeout: 请求超时时间（秒）
            **kwargs: 其他参数
        """
        super().__init__(config, api_key, **kwargs)
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # 初始化HTTP客户端
        self._client: Optional[AsyncClient] = None
    
    @property
    def provider_name(self) -> str:
        """提供商名称"""
        return "Dify"
    
    @property 
    def supported_models(self) -> List[str]:
        """支持的模型列表"""
        return [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4-turbo",
            "claude-3-sonnet",
            "claude-3-opus",
            "custom-model"  # Dify支持自定义模型
        ]
    
    async def _get_client(self) -> AsyncClient:
        """获取HTTP客户端（延迟初始化）"""
        if self._client is None:
            self._client = AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    async def _close_client(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def __del__(self):
        """析构函数，确保客户端关闭"""
        if hasattr(self, '_client') and self._client:
            try:
                asyncio.create_task(self._close_client())
            except:
                pass
    
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
        """
        try:
            client = await self._get_client()
            config = config_override or self.config
            
            # 构建请求体
            request_data = self._build_chat_request(messages, config, stream=False)
            
            # 发送请求
            url = f"{self.base_url}/chat-messages"
            response = await client.post(url, json=request_data)
            
            # 处理响应
            return self._parse_chat_response(response)
            
        except Exception as e:
            logger.error("dify_generate_response_error", error=str(e))
            raise self._handle_exception(e)
    
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
        """
        try:
            client = await self._get_client()
            config = config_override or self.config
            
            # 构建请求体
            request_data = self._build_chat_request(messages, config, stream=True)
            
            # 发送流式请求
            url = f"{self.base_url}/chat-messages"
            
            async with client.stream(
                "POST", url, json=request_data
            ) as response:
                
                if response.status_code != 200:
                    raise self._handle_http_error(response)
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # 移除"data: "前缀
                        
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            
                            # 检查事件类型
                            if data.get("event") == "message":
                                content = data.get("answer", "")
                                if content:
                                    yield content
                                    
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error("dify_generate_stream_response_error", error=str(e))
            raise self._handle_exception(e)
    
    async def validate_config(self) -> bool:
        """
        验证配置有效性
        
        Returns:
            bool: 配置是否有效
        """
        try:
            client = await self._get_client()
            
            # 发送测试请求
            test_messages = [LLMMessage(role="user", content="Hello")]
            request_data = self._build_chat_request(test_messages, self.config, stream=False)
            
            url = f"{self.base_url}/chat-messages"
            response = await client.post(url, json=request_data)
            
            return response.status_code == 200
            
        except Exception as e:
            logger.warning("dify_config_validation_failed", error=str(e))
            return False
    
    async def get_token_count(self, text: str) -> int:
        """
        计算文本的token数量
        
        Args:
            text: 输入文本
            
        Returns:
            int: token数量
        """
        try:
            client = await self._get_client()
            
            # Dify token计算API
            url = f"{self.base_url}/parameters"
            response = await client.get(url)
            
            if response.status_code == 200:
                # 简单估算（如果API不支持具体计算）
                return len(text) // 4  # 粗略估算：4字符=1token
            else:
                # 使用基类的估算方法
                return super().estimate_context_tokens([LLMMessage(role="user", content=text)])
                
        except Exception:
            # 降级到基类方法
            return super().estimate_context_tokens([LLMMessage(role="user", content=text)])
    
    def _build_chat_request(
        self, 
        messages: List[LLMMessage], 
        config: LLMConfig, 
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        构建Dify聊天请求体
        
        Args:
            messages: 消息列表
            config: LLM配置
            stream: 是否使用流式响应
            
        Returns:
            Dict[str, Any]: 请求体
        """
        # 提取最后一条用户消息作为query
        user_messages = [msg for msg in messages if msg.role == "user"]
        if not user_messages:
            raise LLMInvalidRequestError("No user message found", self.provider_name)
        
        query = user_messages[-1].content
        
        # 构建对话历史
        conversation_history = []
        for i, msg in enumerate(messages[:-1]):  # 排除最后一条消息
            if msg.role == "user":
                conversation_history.append({
                    "query": msg.content,
                    "answer": ""
                })
            elif msg.role == "assistant" and conversation_history:
                conversation_history[-1]["answer"] = msg.content
        
        # 构建请求体
        request_data = {
            "inputs": {},
            "query": query,
            "response_mode": "streaming" if stream else "blocking",
            "conversation_id": "",  # 让Dify自动生成
            "user": "api_user"
        }
        
        # 添加对话历史
        if conversation_history:
            request_data["conversation_id"] = self._generate_conversation_id(messages)
        
        # 添加模型参数
        if hasattr(config, 'temperature'):
            request_data["inputs"]["temperature"] = config.temperature
        if hasattr(config, 'max_tokens') and config.max_tokens:
            request_data["inputs"]["max_tokens"] = config.max_tokens
        
        # 添加自定义参数
        if config.custom_params:
            request_data["inputs"].update(config.custom_params)
        
        return request_data
    
    def _generate_conversation_id(self, messages: List[LLMMessage]) -> str:
        """
        生成对话ID（基于消息内容的hash）
        
        Args:
            messages: 消息列表
            
        Returns:
            str: 对话ID
        """
        # 使用消息内容生成简单hash作为对话ID
        content = "".join(msg.content for msg in messages[:5])  # 取前5条消息
        return f"conv_{hash(content) % 1000000:06d}"
    
    def _parse_chat_response(self, response: httpx.Response) -> LLMResponse:
        """
        解析Dify聊天响应
        
        Args:
            response: HTTP响应
            
        Returns:
            LLMResponse: 解析后的响应
        """
        if response.status_code != 200:
            raise self._handle_http_error(response)
        
        try:
            data = response.json()
            
            content = data.get("answer", "")
            usage_info = data.get("metadata", {}).get("usage", {})
            
            return LLMResponse(
                content=content,
                finish_reason="stop",
                usage={
                    "prompt_tokens": usage_info.get("prompt_tokens", 0),
                    "completion_tokens": usage_info.get("completion_tokens", 0),
                    "total_tokens": usage_info.get("total_tokens", 0)
                },
                metadata={
                    "conversation_id": data.get("conversation_id"),
                    "message_id": data.get("message_id"),
                    "created_at": data.get("created_at")
                }
            )
            
        except (KeyError, json.JSONDecodeError) as e:
            raise LLMProviderError(
                f"Failed to parse response: {str(e)}", 
                self.provider_name
            )
    
    def _handle_http_error(self, response: httpx.Response) -> LLMProviderError:
        """
        处理HTTP错误响应
        
        Args:
            response: HTTP响应
            
        Returns:
            LLMProviderError: 相应的异常
        """
        try:
            error_data = response.json()
            error_message = error_data.get("message", "Unknown error")
            error_code = error_data.get("code")
        except:
            error_message = f"HTTP {response.status_code}"
            error_code = str(response.status_code)
        
        if response.status_code == 429:
            return LLMRateLimitError(error_message, self.provider_name, error_code)
        elif response.status_code == 402:
            return LLMQuotaExceededError(error_message, self.provider_name, error_code)
        elif response.status_code == 400:
            return LLMInvalidRequestError(error_message, self.provider_name, error_code)
        else:
            return LLMProviderError(error_message, self.provider_name, error_code)
    
    def _handle_exception(self, exception: Exception) -> LLMProviderError:
        """
        处理其他异常
        
        Args:
            exception: 原始异常
            
        Returns:
            LLMProviderError: 转换后的异常
        """
        if isinstance(exception, LLMProviderError):
            return exception
        elif isinstance(exception, (ConnectTimeout, ReadTimeout)):
            return LLMProviderError(
                f"Request timeout: {str(exception)}", 
                self.provider_name
            )
        elif isinstance(exception, httpx.HTTPError):
            return LLMProviderError(
                f"HTTP error: {str(exception)}", 
                self.provider_name
            )
        else:
            return LLMProviderError(
                f"Unexpected error: {str(exception)}", 
                self.provider_name
            ) 