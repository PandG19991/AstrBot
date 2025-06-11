"""
自动回复服务

基于LLM提供商实现智能自动回复功能，支持多轮对话和上下文管理
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm.base_provider import (
    BaseLLMProvider, 
    LLMConfig, 
    LLMMessage, 
    LLMResponse,
    LLMProviderError
)
from app.services.llm.dify_provider import DifyProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.context_manager import ContextManager
from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.schemas.message import MessageCreate, MessageType

# 配置日志
logger = logging.getLogger(__name__)


class AutoReplyService:
    """自动回复服务"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化自动回复服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.context_manager = ContextManager(db)
        self.message_service = MessageService(db)
        self.session_service = SessionService(db)
        
        # LLM提供商缓存
        self._providers: Dict[str, BaseLLMProvider] = {}
    
    async def generate_reply(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_message: str,
        llm_config: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        auto_save: bool = True
    ) -> str:
        """
        生成自动回复
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            user_message: 用户消息内容
            llm_config: LLM配置信息
            system_prompt: 系统提示词
            auto_save: 是否自动保存消息
            
        Returns:
            str: 生成的回复内容
            
        Raises:
            ValueError: 参数无效
            LLMProviderError: LLM调用失败
        """
        try:
            # 验证输入
            if not user_message.strip():
                raise ValueError("User message cannot be empty")
            
            # 保存用户消息
            if auto_save:
                user_msg_create = MessageCreate(
                    session_id=session_id,
                    content=user_message,
                    message_type=MessageType.user,
                    user_id="system_auto"  # 自动回复场景下的默认用户ID
                )
                await self.message_service.store_message(user_msg_create, tenant_id)
            
            # 获取LLM提供商
            provider = await self._get_llm_provider(tenant_id, llm_config)
            
            # 构建对话上下文
            context = await self._build_conversation_context(
                session_id, 
                tenant_id, 
                system_prompt,
                provider.config.max_tokens or 4000
            )
            
            # 添加当前用户消息
            context.append(LLMMessage(
                role="user",
                content=user_message
            ))
            
            # 生成回复
            response = await provider.generate_response(context)
            reply_content = response.content.strip()
            
            # 内容安全检查
            safe_reply = await self._content_safety_check(reply_content, tenant_id)
            
            # 保存AI回复消息
            if auto_save and safe_reply:
                ai_msg_create = MessageCreate(
                    session_id=session_id,
                    content=safe_reply,
                    message_type=MessageType.agent,
                    user_id="ai_assistant",
                    metadata={
                        "provider": provider.provider_name,
                        "model": provider.config.model,
                        "usage": response.usage,
                        "finish_reason": response.finish_reason
                    }
                )
                await self.message_service.store_message(ai_msg_create, tenant_id)
            
            logger.info("auto_reply_generated", 
                       session_id=session_id,
                       tenant_id=tenant_id,
                       provider=provider.provider_name,
                       input_length=len(user_message),
                       output_length=len(safe_reply),
                       usage=response.usage)
            
            return safe_reply
            
        except Exception as e:
            logger.error("auto_reply_generation_error", 
                        session_id=session_id,
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def generate_stream_reply(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_message: str,
        llm_config: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ):
        """
        生成流式自动回复
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            user_message: 用户消息内容
            llm_config: LLM配置信息
            system_prompt: 系统提示词
            
        Yields:
            str: 回复内容片段
        """
        try:
            # 验证输入
            if not user_message.strip():
                raise ValueError("User message cannot be empty")
            
            # 获取LLM提供商
            provider = await self._get_llm_provider(tenant_id, llm_config)
            
            # 构建对话上下文
            context = await self._build_conversation_context(
                session_id, 
                tenant_id, 
                system_prompt,
                provider.config.max_tokens or 4000
            )
            
            # 添加当前用户消息
            context.append(LLMMessage(
                role="user",
                content=user_message
            ))
            
            # 生成流式回复
            full_response = ""
            async for chunk in provider.generate_stream_response(context):
                # 实时内容检查（基础版本）
                if await self._is_content_safe_chunk(chunk):
                    full_response += chunk
                    yield chunk
            
            # 保存完整的对话记录
            if full_response:
                # 保存用户消息
                user_msg_create = MessageCreate(
                    session_id=session_id,
                    content=user_message,
                    message_type=MessageType.user,
                    user_id="system_auto"
                )
                await self.message_service.store_message(user_msg_create, tenant_id)
                
                # 保存AI回复
                ai_msg_create = MessageCreate(
                    session_id=session_id,
                    content=full_response,
                    message_type=MessageType.agent,
                    user_id="ai_assistant",
                    metadata={
                        "provider": provider.provider_name,
                        "model": provider.config.model,
                        "streaming": True
                    }
                )
                await self.message_service.store_message(ai_msg_create, tenant_id)
            
            logger.info("stream_reply_completed", 
                       session_id=session_id,
                       tenant_id=tenant_id,
                       provider=provider.provider_name,
                       response_length=len(full_response))
            
        except Exception as e:
            logger.error("stream_reply_generation_error", 
                        session_id=session_id,
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def _get_llm_provider(
        self, 
        tenant_id: UUID, 
        llm_config: Optional[Dict[str, Any]] = None
    ) -> BaseLLMProvider:
        """
        获取LLM提供商实例
        
        Args:
            tenant_id: 租户ID
            llm_config: LLM配置信息
            
        Returns:
            BaseLLMProvider: LLM提供商实例
        """
        # 使用默认配置或传入的配置
        config = llm_config or await self._get_default_llm_config(tenant_id)
        
        provider_type = config.get("provider", "openai")
        cache_key = f"{tenant_id}_{provider_type}_{config.get('model', 'default')}"
        
        # 检查缓存
        if cache_key in self._providers:
            return self._providers[cache_key]
        
        # 创建LLM配置对象
        llm_config_obj = LLMConfig(
            model=config.get("model", "gpt-3.5-turbo"),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 2000),
            top_p=config.get("top_p", 1.0),
            frequency_penalty=config.get("frequency_penalty", 0.0),
            presence_penalty=config.get("presence_penalty", 0.0)
        )
        
        # 创建提供商实例
        if provider_type == "dify":
            provider = DifyProvider(
                config=llm_config_obj,
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url", "https://api.dify.ai/v1")
            )
        elif provider_type == "openai":
            provider = OpenAIProvider(
                config=llm_config_obj,
                api_key=config.get("api_key", ""),
                base_url=config.get("base_url", "https://api.openai.com/v1")
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_type}")
        
        # 缓存提供商实例
        self._providers[cache_key] = provider
        
        return provider
    
    async def _get_default_llm_config(self, tenant_id: UUID) -> Dict[str, Any]:
        """
        获取租户的默认LLM配置
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: LLM配置
        """
        # 这里应该从数据库或配置中获取租户的LLM配置
        # 暂时返回默认配置
        return {
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 2000,
            "api_key": "your-api-key",  # 应该从环境变量或配置中获取
            "base_url": "https://api.openai.com/v1"
        }
    
    async def _build_conversation_context(
        self,
        session_id: UUID,
        tenant_id: UUID,
        system_prompt: Optional[str],
        max_tokens: int
    ) -> List[LLMMessage]:
        """
        构建对话上下文
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            system_prompt: 系统提示词
            max_tokens: 最大token数
            
        Returns:
            List[LLMMessage]: 对话上下文
        """
        # 使用默认系统提示词
        if not system_prompt:
            system_prompt = await self._get_default_system_prompt(tenant_id)
        
        # 构建上下文
        context = await self.context_manager.build_context(
            session_id=session_id,
            tenant_id=tenant_id,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            context_window=20,  # 最近20条消息
            include_user_context=True
        )
        
        return context
    
    async def _get_default_system_prompt(self, tenant_id: UUID) -> str:
        """
        获取默认系统提示词
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            str: 系统提示词
        """
        # 这里应该从数据库获取租户自定义的系统提示词
        # 暂时返回通用提示词
        return """你是一个专业的客服助手，请遵循以下原则：
1. 友好、耐心、专业地回答用户问题
2. 如果不确定答案，请诚实告知并建议联系人工客服
3. 保持回复简洁明了，避免冗长
4. 关注用户的真实需求，提供有价值的帮助
5. 如果用户情绪激动，请保持冷静并尝试缓解情况

请用中文回复用户问题。"""
    
    async def _content_safety_check(
        self, 
        content: str, 
        tenant_id: UUID
    ) -> str:
        """
        内容安全检查
        
        Args:
            content: 待检查的内容
            tenant_id: 租户ID
            
        Returns:
            str: 安全的内容
        """
        # 基础的内容安全检查
        # 在实际应用中，这里应该集成专业的内容审核服务
        
        # 敏感词过滤（示例）
        sensitive_words = ["敏感词1", "敏感词2"]  # 应该从配置或数据库加载
        
        filtered_content = content
        for word in sensitive_words:
            if word in filtered_content:
                filtered_content = filtered_content.replace(word, "*" * len(word))
                logger.warning("sensitive_word_filtered", 
                             tenant_id=tenant_id, 
                             word=word)
        
        # 检查内容长度
        if len(filtered_content) > 2000:  # 限制回复长度
            filtered_content = filtered_content[:2000] + "..."
            logger.info("content_truncated", 
                       tenant_id=tenant_id, 
                       original_length=len(content),
                       truncated_length=len(filtered_content))
        
        return filtered_content
    
    async def _is_content_safe_chunk(self, chunk: str) -> bool:
        """
        检查内容片段是否安全（用于流式响应）
        
        Args:
            chunk: 内容片段
            
        Returns:
            bool: 是否安全
        """
        # 简单的实时安全检查
        # 检查是否包含明显的敏感内容
        sensitive_patterns = ["敏感词1", "敏感词2"]
        
        for pattern in sensitive_patterns:
            if pattern in chunk:
                return False
        
        return True
    
    async def is_auto_reply_enabled(
        self, 
        session_id: UUID, 
        tenant_id: UUID
    ) -> bool:
        """
        检查会话是否启用自动回复
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            
        Returns:
            bool: 是否启用自动回复
        """
        try:
            session = await self.session_service.get_session(session_id, tenant_id)
            if not session:
                return False
            
            # 检查会话状态和租户配置
            # 这里应该根据实际业务逻辑判断
            return session.status == "active"
            
        except Exception as e:
            logger.error("check_auto_reply_enabled_error", 
                        session_id=session_id,
                        error=str(e))
            return False
    
    async def get_reply_suggestions(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_message: str,
        suggestion_count: int = 3
    ) -> List[str]:
        """
        获取回复建议（用于客服话术推荐）
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            user_message: 用户消息
            suggestion_count: 建议数量
            
        Returns:
            List[str]: 回复建议列表
        """
        try:
            # 获取LLM提供商
            provider = await self._get_llm_provider(tenant_id)
            
            # 构建提示词
            suggestion_prompt = f"""基于以下用户消息，生成{suggestion_count}个专业的客服回复建议：

用户消息：{user_message}

请生成{suggestion_count}个不同风格的回复选项：
1. 正式专业的回复
2. 友好亲切的回复
3. 简洁直接的回复

每个回复用"---"分隔。"""
            
            # 构建上下文（简化版）
            context = [LLMMessage(
                role="system",
                content="你是一个专业的客服助手，需要为客服人员提供回复建议。"
            )]
            
            context.append(LLMMessage(
                role="user",
                content=suggestion_prompt
            ))
            
            # 生成建议
            response = await provider.generate_response(context)
            
            # 解析建议
            suggestions = response.content.split("---")
            suggestions = [s.strip() for s in suggestions if s.strip()]
            
            # 限制返回数量
            return suggestions[:suggestion_count]
            
        except Exception as e:
            logger.error("get_reply_suggestions_error", 
                        session_id=session_id,
                        error=str(e))
            return [] 