"""
会话数据模型
对应数据库 sessions 表，管理用户与客服的会话
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import Column, String, Enum as SQLEnum, DateTime, JSON, Index, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SessionStatus(str, Enum):
    """会话状态枚举"""
    WAITING = "waiting"         # 等待分配
    ACTIVE = "active"          # 进行中
    TRANSFERRED = "transferred" # 已转接
    CLOSED = "closed"          # 已关闭
    TIMEOUT = "timeout"        # 超时关闭


class ChannelType(str, Enum):
    """渠道类型枚举"""
    DIRECT = "direct"          # 直接对话
    GROUP = "group"            # 群聊
    BROADCAST = "broadcast"    # 广播


class Session(Base):
    """
    会话模型
    
    管理用户与客服的会话，支持跨平台和租户隔离
    
    参考:
    - @cursor doc/database_design/erd_diagram.md SESSIONS表
    - @cursor doc/api_contracts/models/common_models.yaml SessionEntity
    """
    __tablename__ = "sessions"
    
    # 主键
    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        comment="会话唯一标识"
    )
    
    # 🚨 多租户隔离字段 - CRITICAL
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属租户ID"
    )
    
    # 用户信息
    user_id = Column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID（复合主键格式：platform:user_id）"
    )
    
    # 平台信息
    platform = Column(
        String(50),
        nullable=False,
        comment="来源平台类型"
    )
    
    # 会话状态
    status = Column(
        SQLEnum(
            SessionStatus.WAITING,
            SessionStatus.ACTIVE,
            SessionStatus.TRANSFERRED,
            SessionStatus.CLOSED,
            SessionStatus.TIMEOUT,
            name="session_status"
        ),
        nullable=False,
        default=SessionStatus.WAITING,
        comment="会话状态"
    )
    
    # 分配信息
    assigned_staff_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="分配的客服ID"
    )
    
    # 渠道类型
    channel_type = Column(
        SQLEnum(
            ChannelType.DIRECT,
            ChannelType.GROUP,
            ChannelType.BROADCAST,
            name="channel_type"
        ),
        nullable=False,
        default=ChannelType.DIRECT,
        comment="消息渠道类型"
    )
    
    # 优先级（1-10）
    priority = Column(
        Integer,
        nullable=False,
        default=5,
        comment="会话优先级（1-10，数字越大优先级越高）"
    )
    
    # 摘要信息
    context_summary = Column(
        String(1000),
        nullable=True,
        comment="会话摘要"
    )
    
    # 扩展字段
    extra_data = Column(
        JSON,
        nullable=True,
        default=lambda: {},
        comment="平台特定的扩展数据"
    )
    
    # 时间戳字段
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="会话创建时间"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="最后更新时间"
    )
    
    last_message_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后消息时间"
    )
    
    closed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="会话关闭时间"
    )
    
    # 关系定义
    tenant = relationship("Tenant", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    
    # 表级约束和索引
    __table_args__ = (
        # 租户+用户+状态复合索引（查询用户活跃会话）
        Index('ix_session_tenant_user_status', 'tenant_id', 'user_id', 'status'),
        # 租户ID索引 (多租户隔离查询)
        Index('ix_session_tenant_id', 'tenant_id'),
        # 状态索引（查询待分配会话）
        Index('ix_session_status', 'status'),
        # 分配客服索引（查询客服会话）
        Index('ix_session_assigned_staff', 'assigned_staff_id'),
        # 平台索引
        Index('ix_session_platform', 'platform'),
        # 创建时间索引
        Index('ix_session_created_at', 'created_at'),
        # 最后消息时间索引（用于超时检查）
        Index('ix_session_last_message_at', 'last_message_at'),
        # 优先级索引（会话分配优先级排序）
        Index('ix_session_priority', 'priority'),
        
        # 表注释
        {"comment": "会话表 - 用户与客服的会话管理，支持多租户隔离"}
    )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<Session(id={self.id}, tenant_id={self.tenant_id}, status='{self.status}')>"
    
    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"Session {self.id} - {self.status}"
    
    @property
    def is_active(self) -> bool:
        """检查会话是否活跃"""
        return self.status in [SessionStatus.WAITING, SessionStatus.ACTIVE]
    
    @property
    def is_closed(self) -> bool:
        """检查会话是否已关闭"""
        return self.status in [SessionStatus.CLOSED, SessionStatus.TIMEOUT]
    
    @property
    def duration_minutes(self) -> Optional[int]:
        """计算会话持续时间（分钟）"""
        if not self.closed_at:
            # 会话未关闭，计算到当前时间
            end_time = datetime.utcnow()
        else:
            end_time = self.closed_at
        
        if self.created_at:
            delta = end_time - self.created_at.replace(tzinfo=None)
            return int(delta.total_seconds() / 60)
        return None
    
    def assign_staff(self, staff_id: uuid.UUID) -> None:
        """
        分配客服
        
        Args:
            staff_id: 客服ID
        """
        self.assigned_staff_id = staff_id
        if self.status == SessionStatus.WAITING:
            self.status = SessionStatus.ACTIVE
    
    def transfer_to_staff(self, new_staff_id: uuid.UUID) -> None:
        """
        转接给新客服
        
        Args:
            new_staff_id: 新客服ID
        """
        self.assigned_staff_id = new_staff_id
        self.status = SessionStatus.TRANSFERRED
    
    def close_session(self, reason: str = "completed") -> None:
        """
        关闭会话
        
        Args:
            reason: 关闭原因
        """
        self.status = SessionStatus.CLOSED
        self.closed_at = datetime.utcnow()
        self.update_metadata("close_reason", reason)
    
    def timeout_session(self) -> None:
        """标记会话为超时"""
        self.status = SessionStatus.TIMEOUT
        self.closed_at = datetime.utcnow()
        self.update_metadata("close_reason", "timeout")
    
    def update_last_message_time(self) -> None:
        """更新最后消息时间"""
        self.last_message_at = datetime.utcnow()
    
    def to_dict(self, include_metadata: bool = True) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Args:
            include_metadata: 是否包含元数据
            
        Returns:
            Dict[str, Any]: 会话信息字典
        """
        data = {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "user_id": self.user_id,
            "platform": self.platform,
            "status": self.status,
            "assigned_staff_id": str(self.assigned_staff_id) if self.assigned_staff_id else None,
            "channel_type": self.channel_type,
            "priority": self.priority,
            "context_summary": self.context_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "duration_minutes": self.duration_minutes,
            "is_active": self.is_active,
            "is_closed": self.is_closed
        }
        
        if include_metadata and self.extra_data:
            data["extra_data"] = self.extra_data
            
        return data
    
    def update_metadata(self, key: str, value: Any) -> None:
        """
        更新元数据
        
        Args:
            key: 元数据键
            value: 元数据值
        """
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        获取元数据值
        
        Args:
            key: 元数据键
            default: 默认值
            
        Returns:
            Any: 元数据值
        """
        if self.extra_data is None:
            return default
        return self.extra_data.get(key, default)
    
    def update_context_summary(self, summary: str) -> None:
        """
        更新会话摘要
        
        Args:
            summary: 会话摘要
        """
        self.context_summary = summary[:1000] if summary else None  # 限制长度
    
    def set_priority(self, priority: int) -> None:
        """
        设置会话优先级
        
        Args:
            priority: 优先级（1-10）
        """
        if 1 <= priority <= 10:
            self.priority = priority
        else:
            raise ValueError("Priority must be between 1 and 10")
    
    @classmethod
    def create_for_user(
        cls, 
        tenant_id: uuid.UUID, 
        user_id: str, 
        platform: str,
        channel_type: str = ChannelType.DIRECT,
        priority: int = 5
    ) -> "Session":
        """
        为用户创建新会话
        
        Args:
            tenant_id: 租户ID
            user_id: 用户ID（复合格式）
            platform: 平台类型
            channel_type: 渠道类型
            priority: 优先级
            
        Returns:
            Session: 新会话实例
        """
        return cls(
            tenant_id=tenant_id,
            user_id=user_id,
            platform=platform,
            channel_type=channel_type,
            priority=priority,
            status=SessionStatus.WAITING
        ) 