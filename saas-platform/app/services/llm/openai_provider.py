"""
OpenAI LLM提供商实现

集成OpenAI API调用
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


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM提供商实现"""
    
    def __init__(
        self, 
        config: LLMConfig, 
        api_key: str, 
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
        **kwargs
    ):
        """
        初始化OpenAI提供商
        
        Args:
            config: LLM配置
            api_key: OpenAI API密钥
            base_url: OpenAI API基础URL
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
        return "OpenAI"
    
    @property 
    def supported_models(self) -> List[str]:
        """支持的模型列表"""
        return [
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-4",
            "gpt-4-32k",
            "gpt-4-turbo",
            "gpt-4-turbo-preview",
            "gpt-4o",
            "gpt-4o-mini"
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
            url = f"{self.base_url}/chat/completions"
            response = await client.post(url, json=request_data)
            
            # 处理响应
            return self._parse_chat_response(response)
            
        except Exception as e:
            logger.error("openai_generate_response_error", error=str(e))
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
            url = f"{self.base_url}/chat/completions"
            
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
                            
                            # 提取delta内容
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                                    
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error("openai_generate_stream_response_error", error=str(e))
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
            request_data["max_tokens"] = 1  # 最小化请求
            
            url = f"{self.base_url}/chat/completions"
            response = await client.post(url, json=request_data)
            
            return response.status_code == 200
            
        except Exception as e:
            logger.warning("openai_config_validation_failed", error=str(e))
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
            # 使用tiktoken库进行精确计算（如果可用）
            try:
                import tiktoken
                
                # 根据模型选择编码器
                if "gpt-4" in self.config.model:
                    encoding = tiktoken.encoding_for_model("gpt-4")
                else:
                    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
                
                return len(encoding.encode(text))
                
            except ImportError:
                # 如果tiktoken不可用，使用估算方法
                # 英文：约4字符=1token，中文：约1.5字符=1token
                chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
                english_chars = len(text) - chinese_chars
                
                return int(chinese_chars / 1.5 + english_chars / 4)
                
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
        构建OpenAI聊天请求体
        
        Args:
            messages: 消息列表
            config: LLM配置
            stream: 是否使用流式响应
            
        Returns:
            Dict[str, Any]: 请求体
        """
        # 转换消息格式
        openai_messages = []
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # 构建请求体
        request_data = {
            "model": config.model,
            "messages": openai_messages,
            "stream": stream,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "frequency_penalty": config.frequency_penalty,
            "presence_penalty": config.presence_penalty
        }
        
        # 添加可选参数
        if config.max_tokens:
            request_data["max_tokens"] = config.max_tokens
        
        if config.stop_sequences:
            request_data["stop"] = config.stop_sequences
        
        # 添加自定义参数
        if config.custom_params:
            request_data.update(config.custom_params)
        
        return request_data
    
    def _parse_chat_response(self, response: httpx.Response) -> LLMResponse:
        """
        解析OpenAI聊天响应
        
        Args:
            response: HTTP响应
            
        Returns:
            LLMResponse: 解析后的响应
        """
        if response.status_code != 200:
            raise self._handle_http_error(response)
        
        try:
            data = response.json()
            
            choices = data.get("choices", [])
            if not choices:
                raise LLMProviderError("No choices in response", self.provider_name)
            
            choice = choices[0]
            content = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason", "unknown")
            
            usage = data.get("usage", {})
            
            return LLMResponse(
                content=content,
                finish_reason=finish_reason,
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                },
                metadata={
                    "model": data.get("model"),
                    "id": data.get("id"),
                    "created": data.get("created")
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
            error_info = error_data.get("error", {})
            error_message = error_info.get("message", "Unknown error")
            error_code = error_info.get("code") or error_info.get("type")
        except:
            error_message = f"HTTP {response.status_code}"
            error_code = str(response.status_code)
        
        if response.status_code == 429:
            return LLMRateLimitError(error_message, self.provider_name, error_code)
        elif response.status_code == 402 or "insufficient_quota" in str(error_code):
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