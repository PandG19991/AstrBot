"""
上下文管理服务

负责构建LLM推理所需的会话上下文，包含历史消息管理、token预算控制和智能截断
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.message_service import MessageService
from app.services.llm.base_provider import LLMMessage, BaseLLMProvider
from app.schemas.message import MessageRead

# 配置日志
logger = logging.getLogger(__name__)


class ContextManager:
    """上下文管理器，负责构建和管理LLM会话上下文"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化上下文管理器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.message_service = MessageService(db)
    
    async def build_context(
        self,
        session_id: UUID,
        tenant_id: UUID,
        max_tokens: int = 4000,
        system_prompt: Optional[str] = None,
        context_window: Optional[int] = None,
        include_user_context: bool = True
    ) -> List[LLMMessage]:
        """
        构建会话上下文
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            max_tokens: 最大token数量
            system_prompt: 系统提示词
            context_window: 上下文窗口大小（消息条数）
            include_user_context: 是否包含用户上下文信息
            
        Returns:
            List[LLMMessage]: 构建的上下文消息列表
        """
        try:
            # 获取会话历史消息
            messages = await self._get_session_messages(
                session_id, 
                tenant_id, 
                context_window
            )
            
            # 构建基础上下文
            context_messages = []
            
            # 添加系统提示词
            if system_prompt:
                context_messages.append(LLMMessage(
                    role="system",
                    content=system_prompt
                ))
            
            # 添加用户上下文信息
            if include_user_context:
                user_context = await self._build_user_context(session_id, tenant_id)
                if user_context:
                    context_messages.append(LLMMessage(
                        role="system",
                        content=user_context
                    ))
            
            # 转换历史消息
            for msg in messages:
                role = "user" if msg.message_type == "user" else "assistant"
                context_messages.append(LLMMessage(
                    role=role,
                    content=msg.content,
                    metadata={
                        "message_id": str(msg.id),
                        "session_id": str(msg.session_id),
                        "created_at": msg.created_at.isoformat()
                    }
                ))
            
            # Token预算管理和截断
            optimized_context = self._optimize_context_by_tokens(
                context_messages, 
                max_tokens
            )
            
            logger.info("context_built", 
                       session_id=session_id,
                       tenant_id=tenant_id,
                       original_messages=len(context_messages),
                       optimized_messages=len(optimized_context),
                       estimated_tokens=self._estimate_total_tokens(optimized_context))
            
            return optimized_context
            
        except Exception as e:
            logger.error("build_context_error", 
                        session_id=session_id, 
                        tenant_id=tenant_id, 
                        error=str(e))
            raise
    
    async def _get_session_messages(
        self,
        session_id: UUID,
        tenant_id: UUID,
        limit: Optional[int] = None
    ) -> List[MessageRead]:
        """
        获取会话历史消息
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            limit: 消息数量限制
            
        Returns:
            List[MessageRead]: 历史消息列表（按时间正序）
        """
        # 获取消息（默认最近50条）
        messages = await self.message_service.get_session_messages(
            session_id=session_id,
            tenant_id=tenant_id,
            page=1,
            page_size=limit or 50,
            message_type=None
        )
        
        # 按时间正序排序（确保上下文顺序正确）
        return sorted(messages.items, key=lambda x: x.created_at)
    
    async def _build_user_context(
        self, 
        session_id: UUID, 
        tenant_id: UUID
    ) -> Optional[str]:
        """
        构建用户上下文信息
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            
        Returns:
            Optional[str]: 用户上下文描述
        """
        try:
            # 获取会话的基本信息（用户ID、开始时间等）
            from app.services.session_service import SessionService
            session_service = SessionService(self.db)
            
            session = await session_service.get_session(session_id, tenant_id)
            if not session:
                return None
            
            # 构建上下文信息
            context_parts = []
            
            # 会话基本信息
            context_parts.append(f"当前会话开始于: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            context_parts.append(f"用户ID: {session.user_id}")
            
            # 会话状态
            if session.status:
                context_parts.append(f"会话状态: {session.status}")
            
            # 获取用户最近的会话统计（可选）
            recent_sessions = await self._get_user_recent_activity(
                session.user_id, 
                tenant_id
            )
            if recent_sessions:
                context_parts.append(f"用户最近活跃度: {recent_sessions}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.warning("build_user_context_error", 
                          session_id=session_id, 
                          error=str(e))
            return None
    
    async def _get_user_recent_activity(
        self, 
        user_id: str, 
        tenant_id: UUID
    ) -> Optional[str]:
        """
        获取用户最近活动统计
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            
        Returns:
            Optional[str]: 活动描述
        """
        try:
            # 获取用户最近7天的会话数量
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            # 这里可以添加更复杂的用户行为分析
            # 暂时返回简单描述
            return "活跃用户"
            
        except Exception:
            return None
    
    def _optimize_context_by_tokens(
        self, 
        messages: List[LLMMessage], 
        max_tokens: int
    ) -> List[LLMMessage]:
        """
        根据token限制优化上下文
        
        Args:
            messages: 原始消息列表
            max_tokens: 最大token限制
            
        Returns:
            List[LLMMessage]: 优化后的消息列表
        """
        if not messages:
            return []
        
        # 分离系统消息和对话消息
        system_messages = [msg for msg in messages if msg.role == "system"]
        conversation_messages = [msg for msg in messages if msg.role != "system"]
        
        # 计算系统消息的token数
        system_tokens = self._estimate_total_tokens(system_messages)
        remaining_tokens = max_tokens - system_tokens
        
        if remaining_tokens <= 0:
            # 如果系统消息已经超出限制，只保留最重要的系统消息
            logger.warning("system_messages_exceed_limit", 
                          system_tokens=system_tokens, 
                          max_tokens=max_tokens)
            return self._truncate_system_messages(system_messages, max_tokens)
        
        # 从最新消息开始，逐步添加对话消息
        selected_conversation = []
        current_tokens = 0
        
        for msg in reversed(conversation_messages):
            msg_tokens = self._estimate_message_tokens(msg)
            
            if current_tokens + msg_tokens <= remaining_tokens:
                selected_conversation.insert(0, msg)  # 保持时间顺序
                current_tokens += msg_tokens
            else:
                # 尝试智能截断当前消息
                truncated_msg = self._truncate_message(
                    msg, 
                    remaining_tokens - current_tokens
                )
                if truncated_msg:
                    selected_conversation.insert(0, truncated_msg)
                break
        
        # 合并系统消息和对话消息
        result = system_messages + selected_conversation
        
        logger.debug("context_optimized", 
                    original_messages=len(messages),
                    optimized_messages=len(result),
                    estimated_tokens=self._estimate_total_tokens(result),
                    max_tokens=max_tokens)
        
        return result
    
    def _truncate_system_messages(
        self, 
        system_messages: List[LLMMessage], 
        max_tokens: int
    ) -> List[LLMMessage]:
        """
        截断系统消息（保留最重要的）
        
        Args:
            system_messages: 系统消息列表
            max_tokens: 最大token数
            
        Returns:
            List[LLMMessage]: 截断后的系统消息
        """
        if not system_messages:
            return []
        
        # 简单策略：保留第一条系统消息（通常是最重要的）
        first_msg = system_messages[0]
        first_msg_tokens = self._estimate_message_tokens(first_msg)
        
        if first_msg_tokens <= max_tokens:
            return [first_msg]
        else:
            # 截断第一条消息的内容
            truncated = self._truncate_message(first_msg, max_tokens)
            return [truncated] if truncated else []
    
    def _truncate_message(
        self, 
        message: LLMMessage, 
        max_tokens: int
    ) -> Optional[LLMMessage]:
        """
        截断单条消息内容
        
        Args:
            message: 原始消息
            max_tokens: 最大token数
            
        Returns:
            Optional[LLMMessage]: 截断后的消息
        """
        if max_tokens <= 0:
            return None
        
        content = message.content
        estimated_tokens = self._estimate_message_tokens(message)
        
        if estimated_tokens <= max_tokens:
            return message
        
        # 简单截断：按比例截取内容
        ratio = max_tokens / estimated_tokens * 0.9  # 留10%缓冲
        truncate_length = int(len(content) * ratio)
        
        if truncate_length < 10:  # 太短的内容没有意义
            return None
        
        truncated_content = content[:truncate_length] + "..."
        
        return LLMMessage(
            role=message.role,
            content=truncated_content,
            metadata=message.metadata
        )
    
    def _estimate_message_tokens(self, message: LLMMessage) -> int:
        """
        估算单条消息的token数
        
        Args:
            message: 消息对象
            
        Returns:
            int: 估算的token数
        """
        # 中英文混合的简单估算
        content = message.content
        
        # 统计中文字符（每个中文字符约1个token）
        chinese_chars = sum(1 for char in content if '\u4e00' <= char <= '\u9fff')
        
        # 统计英文字符（约4个字符1个token）
        english_chars = len(content) - chinese_chars
        
        # 估算total tokens（包含role等元数据的开销）
        content_tokens = chinese_chars + english_chars // 4
        
        # 加上角色和格式的token开销
        overhead = 10  # role、格式化等的开销
        
        return content_tokens + overhead
    
    def _estimate_total_tokens(self, messages: List[LLMMessage]) -> int:
        """
        估算消息列表的总token数
        
        Args:
            messages: 消息列表
            
        Returns:
            int: 估算的总token数
        """
        return sum(self._estimate_message_tokens(msg) for msg in messages)
    
    async def get_context_summary(
        self,
        session_id: UUID,
        tenant_id: UUID,
        max_summary_length: int = 200
    ) -> Optional[str]:
        """
        生成会话上下文摘要
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID  
            max_summary_length: 最大摘要长度
            
        Returns:
            Optional[str]: 会话摘要
        """
        try:
            messages = await self._get_session_messages(session_id, tenant_id, 20)
            
            if not messages:
                return None
            
            # 简单的摘要生成（可以后续集成LLM生成摘要）
            user_messages = [msg for msg in messages if msg.message_type == "user"]
            
            if user_messages:
                # 取最近几条用户消息作为摘要
                recent_queries = [msg.content[:50] for msg in user_messages[-3:]]
                summary = "用户最近咨询: " + "; ".join(recent_queries)
                
                if len(summary) > max_summary_length:
                    summary = summary[:max_summary_length] + "..."
                
                return summary
            
            return None
            
        except Exception as e:
            logger.error("get_context_summary_error", 
                        session_id=session_id, 
                        error=str(e))
            return None 