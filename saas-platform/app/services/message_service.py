"""
消息管理服务层
实现消息的存储、检索、处理和业务逻辑
参考：cursor doc/功能说明.md 3.2 会话与消息管理
"""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_, desc
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status, Depends

from app.models.message import Message, MessageType, MessageStatus
from app.models.session import Session
from app.schemas.message import (
    MessageCreate,
    MessageRead,
    MessageUpdate,
    IncomingMessageData
)
from app.services.session_service import SessionService, get_session_service
from app.core.database import get_db_session
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MessageService:
    """消息管理服务"""
    
    def __init__(self, db: AsyncSession, session_service: SessionService):
        """初始化消息服务
        
        Args:
            db: 数据库异步会话
            session_service: 会话服务实例
        """
        self.db = db
        self.session_service = session_service
    
    async def store_message(
        self, 
        message_data: MessageCreate, 
        tenant_id: UUID
    ) -> MessageRead:
        """存储消息到数据库
        
        根据功能说明.md要求，实现消息的持久化存储
        
        Args:
            message_data: 消息创建数据
            tenant_id: 租户ID（多租户隔离）
            
        Returns:
            MessageRead: 存储的消息信息
            
        Raises:
            HTTPException: 存储失败或权限不足时
        """
        try:
            # 1. 验证会话是否属于当前租户
            session = await self.session_service.get_session(
                message_data.session_id, 
                tenant_id
            )
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="会话不存在或没有访问权限"
                )
            
            # 2. 创建消息记录
            message = Message(
                id=uuid4(),
                tenant_id=tenant_id,
                session_id=message_data.session_id,
                message_type=message_data.message_type,
                content=message_data.content,
                sender_type=message_data.sender_type,
                sender_id=message_data.sender_id,
                sender_name=message_data.sender_name,
                created_at=datetime.utcnow(),
                status=MessageStatus.SENT,
                # 可选字段
                metadata=message_data.metadata or {},
                attachments=message_data.attachments or [],
                reply_to_id=message_data.reply_to_id
            )
            
            self.db.add(message)
            
            # 3. 更新会话的最后消息时间
            await self.session_service.update_last_message_time(
                message_data.session_id, 
                tenant_id
            )
            
            await self.db.commit()
            await self.db.refresh(message)
            
            logger.info(
                "消息存储成功",
                message_id=str(message.id),
                session_id=str(message_data.session_id),
                message_type=message_data.message_type.value,
                sender_type=message_data.sender_type.value,
                tenant_id=str(tenant_id)
            )
            
            return MessageRead.model_validate(message)
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "消息存储失败",
                session_id=str(message_data.session_id),
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="消息存储失败，请稍后重试"
            )
    
    async def get_session_messages(
        self,
        session_id: UUID,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 50,
        message_type: Optional[MessageType] = None,
        before_time: Optional[datetime] = None,
        after_time: Optional[datetime] = None
    ) -> List[MessageRead]:
        """获取会话消息列表
        
        支持分页、时间范围和类型过滤
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID（隔离检查）
            skip: 跳过记录数
            limit: 每页记录数
            message_type: 消息类型过滤
            before_time: 时间范围过滤（之前）
            after_time: 时间范围过滤（之后）
            
        Returns:
            List[MessageRead]: 消息列表（按时间倒序）
        """
        try:
            # 1. 验证会话权限
            session = await self.session_service.get_session(session_id, tenant_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="会话不存在或没有访问权限"
                )
            
            # 2. 构建查询条件
            conditions = [
                Message.session_id == session_id,
                Message.tenant_id == tenant_id
            ]
            
            if message_type:
                conditions.append(Message.message_type == message_type)
            
            if before_time:
                conditions.append(Message.created_at < before_time)
                
            if after_time:
                conditions.append(Message.created_at > after_time)
            
            # 3. 执行查询
            query = (
                select(Message)
                .where(and_(*conditions))
                .order_by(desc(Message.created_at))
                .offset(skip)
                .limit(limit)
            )
            
            result = await self.db.execute(query)
            messages = result.scalars().all()
            
            logger.info(
                "会话消息获取成功",
                session_id=str(session_id),
                tenant_id=str(tenant_id),
                returned_count=len(messages),
                skip=skip,
                limit=limit
            )
            
            return [MessageRead.model_validate(message) for message in messages]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "获取会话消息失败",
                session_id=str(session_id),
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取消息列表失败"
            )
    
    async def process_incoming_message(
        self,
        incoming_data: IncomingMessageData,
        tenant_id: UUID
    ) -> MessageRead:
        """处理incoming消息的完整业务流程
        
        实现功能说明.md中描述的消息处理流程：
        1. 黑名单检查
        2. 会话创建/更新
        3. 消息存储
        4. 通知推送
        
        Args:
            incoming_data: Incoming消息数据
            tenant_id: 租户ID
            
        Returns:
            MessageRead: 处理后的消息
        """
        try:
            logger.info(
                "开始处理incoming消息",
                user_id=incoming_data.user_id,
                platform=incoming_data.platform,
                message_type=incoming_data.message_type.value,
                tenant_id=str(tenant_id)
            )
            
            # 1. 黑名单检查 (TODO: 后续实现黑名单服务时集成)
            # is_blocked = await blacklist_service.check_user(
            #     incoming_data.user_id, 
            #     incoming_data.platform, 
            #     tenant_id
            # )
            # if is_blocked:
            #     logger.warning("用户在黑名单中，消息被拦截")
            #     return await self._store_blocked_message(incoming_data, tenant_id)
            
            # 2. 获取或创建会话
            session = await self.session_service.create_or_get_session(
                user_id=incoming_data.user_id,
                platform=incoming_data.platform,
                tenant_id=tenant_id,
                session_data=incoming_data.session_data
            )
            
            # 3. 创建消息数据
            message_data = MessageCreate(
                session_id=session.id,
                message_type=incoming_data.message_type,
                content=incoming_data.content,
                sender_type=incoming_data.sender_type,
                sender_id=incoming_data.user_id,
                sender_name=incoming_data.sender_name,
                metadata=incoming_data.metadata,
                attachments=incoming_data.attachments
            )
            
            # 4. 存储消息
            stored_message = await self.store_message(message_data, tenant_id)
            
            # 5. 触发通知推送 (TODO: 后续实现WebSocket推送时集成)
            # await notification_service.push_message_to_agents(
            #     stored_message, 
            #     session, 
            #     tenant_id
            # )
            
            logger.info(
                "incoming消息处理完成",
                message_id=str(stored_message.id),
                session_id=str(session.id),
                user_id=incoming_data.user_id,
                tenant_id=str(tenant_id)
            )
            
            return stored_message
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "处理incoming消息失败",
                user_id=incoming_data.user_id,
                platform=incoming_data.platform,
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="消息处理失败，请稍后重试"
            )
    
    async def search_messages(
        self,
        tenant_id: UUID,
        search_query: str,
        session_id: Optional[UUID] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[MessageRead]:
        """搜索消息
        
        根据功能说明.md要求，实现消息的全文搜索功能
        
        Args:
            tenant_id: 租户ID（隔离）
            search_query: 搜索关键词
            session_id: 会话过滤
            user_id: 用户过滤
            start_time: 开始时间
            end_time: 结束时间
            skip: 跳过记录数
            limit: 每页记录数
            
        Returns:
            List[MessageRead]: 搜索结果
        """
        try:
            # 构建搜索条件
            conditions = [Message.tenant_id == tenant_id]
            
            # 关键词搜索（简单的LIKE搜索，后续可优化为全文搜索）
            if search_query:
                conditions.append(
                    Message.content.ilike(f"%{search_query}%")
                )
            
            if session_id:
                conditions.append(Message.session_id == session_id)
                
            if user_id:
                conditions.append(Message.sender_id == user_id)
                
            if start_time:
                conditions.append(Message.created_at >= start_time)
                
            if end_time:
                conditions.append(Message.created_at <= end_time)
            
            # 执行搜索
            query = (
                select(Message)
                .where(and_(*conditions))
                .order_by(desc(Message.created_at))
                .offset(skip)
                .limit(limit)
            )
            
            result = await self.db.execute(query)
            messages = result.scalars().all()
            
            logger.info(
                "消息搜索完成",
                tenant_id=str(tenant_id),
                search_query=search_query,
                returned_count=len(messages)
            )
            
            return [MessageRead.model_validate(message) for message in messages]
            
        except Exception as e:
            logger.error(
                "消息搜索失败",
                tenant_id=str(tenant_id),
                search_query=search_query,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="消息搜索失败"
            )
    
    async def update_message_status(
        self,
        message_id: UUID,
        tenant_id: UUID,
        new_status: MessageStatus
    ) -> MessageRead:
        """更新消息状态
        
        Args:
            message_id: 消息ID
            tenant_id: 租户ID（隔离检查）
            new_status: 新状态
            
        Returns:
            MessageRead: 更新后的消息
        """
        try:
            # 获取消息并验证权限
            query = select(Message).where(
                and_(
                    Message.id == message_id,
                    Message.tenant_id == tenant_id
                )
            )
            result = await self.db.execute(query)
            message = result.scalar_one_or_none()
            
            if not message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="消息不存在或没有访问权限"
                )
            
            # 更新状态
            message.status = new_status
            message.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(message)
            
            logger.info(
                "消息状态更新成功",
                message_id=str(message_id),
                new_status=new_status.value,
                tenant_id=str(tenant_id)
            )
            
            return MessageRead.model_validate(message)
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "消息状态更新失败",
                message_id=str(message_id),
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="消息状态更新失败"
            )
    
    async def get_message_statistics(
        self,
        tenant_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """获取消息统计信息
        
        Args:
            tenant_id: 租户ID
            start_time: 统计开始时间
            end_time: 统计结束时间
            
        Returns:
            Dict[str, Any]: 统计数据
        """
        try:
            conditions = [Message.tenant_id == tenant_id]
            
            if start_time:
                conditions.append(Message.created_at >= start_time)
            if end_time:
                conditions.append(Message.created_at <= end_time)
            
            # 基础统计查询
            total_query = select(func.count(Message.id)).where(and_(*conditions))
            total_result = await self.db.execute(total_query)
            total_messages = total_result.scalar()
            
            # 按类型统计
            type_query = (
                select(Message.message_type, func.count(Message.id))
                .where(and_(*conditions))
                .group_by(Message.message_type)
            )
            type_result = await self.db.execute(type_query)
            type_stats = {row[0].value: row[1] for row in type_result.fetchall()}
            
            # 按发送者类型统计
            sender_query = (
                select(Message.sender_type, func.count(Message.id))
                .where(and_(*conditions))
                .group_by(Message.sender_type)
            )
            sender_result = await self.db.execute(sender_query)
            sender_stats = {row[0].value: row[1] for row in sender_result.fetchall()}
            
            statistics = {
                "total_messages": total_messages,
                "message_types": type_stats,
                "sender_types": sender_stats,
                "period": {
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat() if end_time else None
                }
            }
            
            logger.info(
                "消息统计获取成功",
                tenant_id=str(tenant_id),
                total_messages=total_messages
            )
            
            return statistics
            
        except Exception as e:
            logger.error(
                "获取消息统计失败",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取消息统计失败"
            )


async def get_message_service(
    db: AsyncSession = Depends(get_db_session),
    session_service: SessionService = Depends(get_session_service)
) -> MessageService:
    """消息服务依赖注入
    
    Returns:
        MessageService: 消息服务实例
    """
    return MessageService(db, session_service) 