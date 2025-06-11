"""
会话管理服务层
实现会话的生命周期管理、状态控制和业务逻辑
参考：cursor doc/功能说明.md 3.2 会话与消息管理
"""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_, update
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status, Depends

from app.models.session import Session, SessionStatus, ChannelType
from app.models.message import Message
from app.models.tenant import Tenant
from app.schemas.session import (
    SessionCreate, 
    SessionRead, 
    SessionUpdate,
    SessionStatusUpdate
)
from app.core.database import get_db_session
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SessionService:
    """会话管理服务"""
    
    def __init__(self, db: AsyncSession):
        """初始化会话服务
        
        Args:
            db: 数据库异步会话
        """
        self.db = db
    
    async def create_or_get_session(
        self, 
        user_id: str, 
        platform: str, 
        tenant_id: UUID,
        session_data: Optional[SessionCreate] = None
    ) -> SessionRead:
        """创建或获取会话（幂等性）
        
        根据功能说明.md要求，支持会话的创建或获取逻辑
        
        Args:
            user_id: 用户ID（平台唯一标识）
            platform: IM平台类型
            tenant_id: 租户ID（多租户隔离）
            session_data: 可选的会话创建数据
            
        Returns:
            SessionRead: 会话信息
            
        Raises:
            HTTPException: 创建失败时
        """
        try:
            # 1. 查找当前用户的活跃会话
            existing_session = await self._get_active_session(user_id, platform, tenant_id)
            
            if existing_session:
                logger.info(
                    "返回现有活跃会话",
                    session_id=str(existing_session.id),
                    user_id=user_id,
                    platform=platform,
                    tenant_id=str(tenant_id)
                )
                return SessionRead.model_validate(existing_session)
            
            # 2. 创建新会话
            session = Session(
                id=uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                platform=platform,
                status=SessionStatus.WAITING,
                channel_type=ChannelType.DIRECT,  # 默认直接对话
                priority=5,  # 默认优先级
                # 扩展数据存储在extra_data中
                extra_data={
                    "customer_name": session_data.customer_name if session_data and hasattr(session_data, 'customer_name') else None,
                    "customer_avatar": session_data.customer_avatar if session_data and hasattr(session_data, 'customer_avatar') else None,
                    "tags": session_data.tags if session_data and hasattr(session_data, 'tags') else [],
                    "metadata": session_data.metadata if session_data and hasattr(session_data, 'metadata') else {}
                }
            )
            
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)
            
            logger.info(
                "会话创建成功",
                session_id=str(session.id),
                user_id=user_id,
                platform=platform,
                tenant_id=str(tenant_id),
                status=session.status.value
            )
            
            return SessionRead.model_validate(session)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "创建或获取会话失败",
                user_id=user_id,
                platform=platform,
                tenant_id=str(tenant_id),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="会话创建失败，请稍后重试"
            )
    
    async def update_session_status(
        self, 
        session_id: UUID, 
        tenant_id: UUID,
        status_update: SessionStatusUpdate
    ) -> SessionRead:
        """更新会话状态
        
        实现会话状态管理，支持状态转换验证
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID（隔离检查）
            status_update: 状态更新数据
            
        Returns:
            SessionRead: 更新后的会话信息
            
        Raises:
            HTTPException: 会话不存在或状态转换无效时
        """
        try:
            # 1. 获取现有会话并验证租户隔离
            session = await self._get_session_with_tenant_check(session_id, tenant_id)
            
            # 2. 验证状态转换
            old_status = session.status
            new_status = status_update.status
            
            if not self._is_valid_status_transition(old_status, new_status):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的状态转换：{old_status.value} -> {new_status.value}"
                )
            
            # 3. 更新会话状态
            session.status = new_status
            session.updated_at = datetime.utcnow()
            
            # 4. 记录状态转换的额外信息
            if status_update.agent_id:
                session.assigned_staff_id = status_update.agent_id
            
            if status_update.reason:
                if not session.extra_data:
                    session.extra_data = {}
                session.extra_data['status_change_reason'] = status_update.reason
            
            # 5. 特殊状态处理
            if new_status == SessionStatus.CLOSED:
                session.closed_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(session)
            
            logger.info(
                "会话状态更新成功",
                session_id=str(session_id),
                old_status=old_status.value,
                new_status=new_status.value,
                tenant_id=str(tenant_id),
                agent_id=status_update.agent_id
            )
            
            return SessionRead.model_validate(session)
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "更新会话状态失败",
                session_id=str(session_id),
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="会话状态更新失败"
            )
    
    async def get_session(self, session_id: UUID, tenant_id: UUID) -> Optional[SessionRead]:
        """获取会话详情
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID（隔离检查）
            
        Returns:
            Optional[SessionRead]: 会话信息，不存在则返回None
        """
        try:
            query = select(Session).where(
                and_(
                    Session.id == session_id,
                    Session.tenant_id == tenant_id  # 多租户隔离
                )
            )
            result = await self.db.execute(query)
            session = result.scalar_one_or_none()
            
            if not session:
                return None
            
            return SessionRead.model_validate(session)
            
        except Exception as e:
            logger.error(
                "获取会话详情失败",
                session_id=str(session_id),
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取会话详情失败"
            )
    
    async def list_tenant_sessions(
        self,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[SessionStatus] = None,
        agent_id: Optional[UUID] = None,
        platform: Optional[str] = None
    ) -> List[SessionRead]:
        """获取租户会话列表
        
        Args:
            tenant_id: 租户ID
            skip: 跳过记录数
            limit: 每页记录数
            status_filter: 状态过滤
            agent_id: 客服过滤
            platform: 平台过滤
            
        Returns:
            List[SessionRead]: 会话列表
        """
        try:
            # 构建查询条件
            conditions = [Session.tenant_id == tenant_id]
            
            if status_filter:
                conditions.append(Session.status == status_filter)
            
            if agent_id:
                conditions.append(Session.assigned_agent_id == agent_id)
                
            if platform:
                conditions.append(Session.platform == platform)
            
            # 执行查询
            query = (
                select(Session)
                .where(and_(*conditions))
                .order_by(Session.last_message_at.desc())
                .offset(skip)
                .limit(limit)
            )
            
            result = await self.db.execute(query)
            sessions = result.scalars().all()
            
            logger.info(
                "租户会话列表获取成功",
                tenant_id=str(tenant_id),
                returned_count=len(sessions),
                skip=skip,
                limit=limit
            )
            
            return [SessionRead.model_validate(session) for session in sessions]
            
        except Exception as e:
            logger.error(
                "获取租户会话列表失败",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取会话列表失败"
            )
    
    async def update_last_message_time(
        self, 
        session_id: UUID, 
        tenant_id: UUID
    ) -> bool:
        """更新会话最后消息时间
        
        用于消息发送时自动更新会话活跃度
        
        Args:
            session_id: 会话ID
            tenant_id: 租户ID
            
        Returns:
            bool: 更新是否成功
        """
        try:
            query = (
                update(Session)
                .where(
                    and_(
                        Session.id == session_id,
                        Session.tenant_id == tenant_id
                    )
                )
                .values(
                    last_message_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            
            result = await self.db.execute(query)
            await self.db.commit()
            
            updated = result.rowcount > 0
            
            if updated:
                logger.debug(
                    "会话最后消息时间更新成功",
                    session_id=str(session_id),
                    tenant_id=str(tenant_id)
                )
            
            return updated
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "更新会话最后消息时间失败",
                session_id=str(session_id),
                tenant_id=str(tenant_id),
                error=str(e)
            )
            return False
    
    # 私有方法
    async def _get_active_session(
        self, 
        user_id: str, 
        platform: str, 
        tenant_id: UUID
    ) -> Optional[Session]:
        """获取用户的活跃会话"""
        query = select(Session).where(
            and_(
                Session.user_id == user_id,
                Session.platform == platform,
                Session.tenant_id == tenant_id,
                Session.status.in_([SessionStatus.WAITING, SessionStatus.ACTIVE])
            )
        ).order_by(Session.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_session_with_tenant_check(
        self, 
        session_id: UUID, 
        tenant_id: UUID
    ) -> Session:
        """获取会话并验证租户权限"""
        query = select(Session).where(
            and_(
                Session.id == session_id,
                Session.tenant_id == tenant_id
            )
        )
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在或没有访问权限"
            )
        
        return session
    
    def _is_valid_status_transition(
        self, 
        old_status: SessionStatus, 
        new_status: SessionStatus
    ) -> bool:
        """验证会话状态转换是否有效
        
        根据功能说明.md中定义的状态转换规则
        """
        # 定义有效的状态转换映射
        valid_transitions = {
            SessionStatus.WAITING: [SessionStatus.ACTIVE, SessionStatus.CLOSED],
            SessionStatus.ACTIVE: [SessionStatus.CLOSED, SessionStatus.TRANSFERRED],
            SessionStatus.TRANSFERRED: [SessionStatus.ACTIVE, SessionStatus.CLOSED],
            SessionStatus.CLOSED: []  # 已关闭的会话不能转换状态
        }
        
        return new_status in valid_transitions.get(old_status, [])


async def get_session_service(db: AsyncSession = Depends(get_db_session)) -> SessionService:
    """会话服务依赖注入
    
    Returns:
        SessionService: 会话服务实例
    """
    return SessionService(db) 