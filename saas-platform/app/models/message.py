"""
消息数据模型
对应数据库 messages 表，管理会话中的消息
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, String, Enum as SQLEnum, DateTime, JSON, Index, ForeignKey, BigInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = "text"              # 文本消息
    IMAGE = "image"            # 图片
    FILE = "file"              # 文件
    VOICE = "voice"            # 语音
    VIDEO = "video"            # 视频
    LOCATION = "location"      # 位置
    SYSTEM = "system"          # 系统消息


class MessageStatus(str, Enum):
    """消息状态枚举"""
    SENT = "sent"              # 已发送
    DELIVERED = "delivered"    # 已送达
    READ = "read"              # 已读
    FAILED = "failed"          # 发送失败


class SenderType(str, Enum):
    """发送者类型枚举"""
    USER = "user"              # 用户
    STAFF = "staff"            # 客服
    BOT = "bot"                # 机器人
    SYSTEM = "system"          # 系统


class Message(Base):
    """
    消息模型
    
    存储会话中的所有消息，支持多种消息类型和附件
    
    参考:
    - @cursor doc/database_design/erd_diagram.md MESSAGES表
    - @cursor doc/api_contracts/models/common_models.yaml MessageEntity
    """
    __tablename__ = "messages"
    
    # 主键（使用BigInteger以支持大量消息）
    id = Column(
        BigInteger, 
        primary_key=True, 
        autoincrement=True,
        comment="消息唯一标识"
    )
    
    # 🚨 多租户隔离字段 - CRITICAL
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属租户ID"
    )
    
    # 会话关联
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属会话ID"
    )
    
    # 消息内容
    content = Column(
        Text,
        nullable=False,
        comment="消息内容"
    )
    
    # 消息类型
    message_type = Column(
        SQLEnum(
            MessageType.TEXT,
            MessageType.IMAGE,
            MessageType.FILE,
            MessageType.VOICE,
            MessageType.VIDEO,
            MessageType.LOCATION,
            MessageType.SYSTEM,
            name="message_type"
        ),
        nullable=False,
        default=MessageType.TEXT,
        comment="消息类型"
    )
    
    # 发送者信息
    sender_type = Column(
        SQLEnum(
            SenderType.USER,
            SenderType.STAFF,
            SenderType.BOT,
            SenderType.SYSTEM,
            name="sender_type"
        ),
        nullable=False,
        comment="发送者类型"
    )
    
    sender_id = Column(
        String(255),
        nullable=False,
        comment="发送者ID"
    )
    
    # 平台消息ID（原始消息ID）
    platform_message_id = Column(
        String(255),
        nullable=True,
        comment="平台原始消息ID"
    )
    
    # 回复关联
    reply_to_id = Column(
        BigInteger,
        ForeignKey("messages.id"),
        nullable=True,
        comment="回复的消息ID"
    )
    
    # 时间戳（消息实际发送时间）
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="消息时间戳"
    )
    
    # 附件信息（JSON存储）
    attachments = Column(
        JSON,
        nullable=True,
        default=lambda: [],
        comment="消息附件列表"
    )
    
    # 扩展字段
    extra_data = Column(
        JSON,
        nullable=True,
        default=lambda: {},
        comment="消息扩展数据"
    )
    
    # 系统时间戳
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="记录创建时间"
    )
    
    # 关系定义
    tenant = relationship("Tenant")
    session = relationship("Session", back_populates="messages")
    # reply_to = relationship("Message", remote_side=[id])
    
    # 表级约束和索引
    __table_args__ = (
        # 租户+会话+时间复合索引（查询会话消息）
        Index('ix_message_tenant_session_time', 'tenant_id', 'session_id', 'timestamp'),
        # 租户ID索引 (多租户隔离查询)
        Index('ix_message_tenant_id', 'tenant_id'),
        # 会话ID索引（查询会话消息）
        Index('ix_message_session_id', 'session_id'),
        # 发送者索引（查询用户消息）
        Index('ix_message_sender', 'sender_type', 'sender_id'),
        # 时间戳索引（时间范围查询）
        Index('ix_message_timestamp', 'timestamp'),
        # 消息类型索引（按类型筛选）
        Index('ix_message_type', 'message_type'),
        # 平台消息ID索引（去重和查找）
        Index('ix_message_platform_id', 'platform_message_id'),
        # 回复索引
        Index('ix_message_reply_to', 'reply_to_id'),
        
        # 表注释
        {"comment": "消息表 - 会话中的消息记录，支持多租户隔离"}
    )
    
    def __repr__(self) -> str:
        """字符串表示"""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, session_id={self.session_id}, type='{self.message_type}', content='{content_preview}')>"
    
    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"Message {self.id} - {self.sender_type}: {self.content[:30]}..."
    
    @property
    def is_from_user(self) -> bool:
        """检查消息是否来自用户"""
        return self.sender_type == SenderType.USER
    
    @property
    def is_from_staff(self) -> bool:
        """检查消息是否来自客服"""
        return self.sender_type == SenderType.STAFF
    
    @property
    def is_system_message(self) -> bool:
        """检查是否为系统消息"""
        return self.sender_type == SenderType.SYSTEM
    
    @property
    def has_attachments(self) -> bool:
        """检查是否有附件"""
        return bool(self.attachments and len(self.attachments) > 0)
    
    @property
    def attachment_count(self) -> int:
        """获取附件数量"""
        return len(self.attachments) if self.attachments else 0
    
    def to_dict(self, include_metadata: bool = True) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Args:
            include_metadata: 是否包含元数据
            
        Returns:
            Dict[str, Any]: 消息信息字典
        """
        data = {
            "id": self.id,
            "tenant_id": str(self.tenant_id),
            "session_id": str(self.session_id),
            "content": self.content,
            "message_type": self.message_type,
            "sender_type": self.sender_type,
            "sender_id": self.sender_id,
            "platform_message_id": self.platform_message_id,
            "reply_to_id": self.reply_to_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "attachments": self.attachments or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "has_attachments": self.has_attachments,
            "attachment_count": self.attachment_count,
            "is_from_user": self.is_from_user,
            "is_from_staff": self.is_from_staff,
            "is_system_message": self.is_system_message
        }
        
        if include_metadata and self.extra_data:
            data["extra_data"] = self.extra_data
            
        return data
    
    def add_attachment(self, attachment: Dict[str, Any]) -> None:
        """
        添加附件
        
        Args:
            attachment: 附件信息字典
        """
        if self.attachments is None:
            self.attachments = []
        self.attachments.append(attachment)
    
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
    
    def mark_as_read(self, reader_id: str) -> None:
        """
        标记消息为已读
        
        Args:
            reader_id: 阅读者ID
        """
        self.update_metadata(f"read_by_{reader_id}", datetime.utcnow().isoformat())
    
    def is_read_by(self, reader_id: str) -> bool:
        """
        检查消息是否被指定用户读取
        
        Args:
            reader_id: 用户ID
            
        Returns:
            bool: 是否已读
        """
        return self.get_metadata(f"read_by_{reader_id}") is not None
    
    @classmethod
    def create_user_message(
        cls,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        sender_id: str,
        content: str,
        message_type: str = MessageType.TEXT,
        platform_message_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> "Message":
        """
        创建用户消息
        
        Args:
            tenant_id: 租户ID
            session_id: 会话ID
            sender_id: 发送者ID
            content: 消息内容
            message_type: 消息类型
            platform_message_id: 平台消息ID
            timestamp: 消息时间戳
            attachments: 附件列表
            
        Returns:
            Message: 新消息实例
        """
        return cls(
            tenant_id=tenant_id,
            session_id=session_id,
            content=content,
            message_type=message_type,
            sender_type=SenderType.USER,
            sender_id=sender_id,
            platform_message_id=platform_message_id,
            timestamp=timestamp or datetime.utcnow(),
            attachments=attachments or []
        )
    
    @classmethod
    def create_staff_message(
        cls,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        staff_id: str,
        content: str,
        message_type: str = MessageType.TEXT,
        reply_to_id: Optional[int] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> "Message":
        """
        创建客服消息
        
        Args:
            tenant_id: 租户ID
            session_id: 会话ID
            staff_id: 客服ID
            content: 消息内容
            message_type: 消息类型
            reply_to_id: 回复的消息ID
            attachments: 附件列表
            
        Returns:
            Message: 新消息实例
        """
        return cls(
            tenant_id=tenant_id,
            session_id=session_id,
            content=content,
            message_type=message_type,
            sender_type=SenderType.STAFF,
            sender_id=staff_id,
            reply_to_id=reply_to_id,
            timestamp=datetime.utcnow(),
            attachments=attachments or []
        )
    
    @classmethod
    def create_system_message(
        cls,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        content: str,
        system_type: str = "system"
    ) -> "Message":
        """
        创建系统消息
        
        Args:
            tenant_id: 租户ID
            session_id: 会话ID
            content: 消息内容
            system_type: 系统类型标识
            
        Returns:
            Message: 新消息实例
        """
        return cls(
            tenant_id=tenant_id,
            session_id=session_id,
            content=content,
            message_type=MessageType.SYSTEM,
            sender_type=SenderType.SYSTEM,
            sender_id=system_type,
            timestamp=datetime.utcnow()
        ) 