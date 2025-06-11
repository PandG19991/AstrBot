"""
消息数据模式定义

包含消息相关的请求和响应数据模型
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.message import MessageType, MessageStatus, SenderType


class MessageCreate(BaseModel):
    """创建消息的请求模型"""
    
    session_id: UUID = Field(..., description="目标会话ID")
    message_type: MessageType = Field(MessageType.TEXT, description="消息类型")
    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")
    sender_type: SenderType = Field(..., description="发送者类型")
    sender_id: str = Field(..., min_length=1, max_length=255, description="发送者ID")
    sender_name: Optional[str] = Field(None, max_length=100, description="发送者名称")
    reply_to_id: Optional[int] = Field(None, description="回复的消息ID")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="附件信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    timestamp: Optional[datetime] = Field(None, description="消息时间戳")
    platform_message_id: Optional[str] = Field(None, max_length=255, description="平台原始消息ID")


class MessageRead(BaseModel):
    """消息响应模型"""
    
    id: int = Field(..., description="消息唯一标识")
    tenant_id: UUID = Field(..., description="所属租户ID")
    session_id: UUID = Field(..., description="所属会话ID")
    message_type: MessageType = Field(..., description="消息类型")
    content: str = Field(..., description="消息内容")
    sender_type: SenderType = Field(..., description="发送者类型")
    sender_id: str = Field(..., description="发送者ID")
    sender_name: Optional[str] = Field(None, description="发送者名称")
    reply_to_id: Optional[int] = Field(None, description="回复的消息ID")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="附件信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    timestamp: datetime = Field(..., description="消息时间戳")
    platform_message_id: Optional[str] = Field(None, description="平台原始消息ID")
    created_at: datetime = Field(..., description="记录创建时间")
    
    # 计算属性
    is_from_user: bool = Field(..., description="是否来自用户")
    is_from_staff: bool = Field(..., description="是否来自客服")
    is_system_message: bool = Field(..., description="是否为系统消息")
    has_attachments: bool = Field(..., description="是否有附件")
    attachment_count: int = Field(..., description="附件数量")

    class Config:
        from_attributes = True


class IncomingMessageData(BaseModel):
    """处理incoming消息的请求模型"""
    
    user_id: str = Field(..., min_length=1, max_length=200, description="用户ID（平台唯一标识）")
    platform: str = Field(..., min_length=1, max_length=50, description="IM平台类型")
    message_type: MessageType = Field(MessageType.TEXT, description="消息类型")
    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")
    sender_name: Optional[str] = Field(None, max_length=100, description="发送者名称")
    attachments: List[Dict[str, Any]] = Field(default_factory=list, description="附件信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    timestamp: Optional[datetime] = Field(None, description="消息时间戳")
    platform_message_id: Optional[str] = Field(None, max_length=255, description="平台原始消息ID")
    
    # 会话数据（如果需要创建新会话）
    session_data: Optional[Dict[str, Any]] = Field(None, description="会话创建数据")


class MessageSearchParams(BaseModel):
    """消息搜索参数模型"""
    
    search_query: str = Field(..., min_length=1, max_length=500, description="搜索关键词")
    session_id: Optional[UUID] = Field(None, description="限制在特定会话")
    user_id: Optional[str] = Field(None, max_length=255, description="按发送用户过滤")
    message_type: Optional[MessageType] = Field(None, description="按消息类型过滤")
    sender_type: Optional[SenderType] = Field(None, description="按发送者类型过滤")
    start_time: Optional[datetime] = Field(None, description="搜索开始时间")
    end_time: Optional[datetime] = Field(None, description="搜索结束时间")
    skip: int = Field(0, ge=0, description="跳过的记录数")
    limit: int = Field(50, ge=1, le=100, description="每页记录数")
    include_metadata: bool = Field(True, description="是否包含元数据")


class MessageStatusUpdate(BaseModel):
    """消息状态更新模型"""
    
    status: MessageStatus = Field(..., description="新的消息状态")
    reader_id: Optional[str] = Field(None, max_length=255, description="读取者ID（用于已读状态）")
    updated_by: Optional[str] = Field(None, max_length=255, description="更新者ID")
    reason: Optional[str] = Field(None, max_length=500, description="状态更新原因")


class MessageUpdate(BaseModel):
    """消息更新模型"""
    
    content: Optional[str] = Field(None, min_length=1, max_length=10000, description="更新消息内容")
    message_type: Optional[MessageType] = Field(None, description="更新消息类型")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="更新附件信息")
    metadata: Optional[Dict[str, Any]] = Field(None, description="更新扩展元数据")
    status: Optional[MessageStatus] = Field(None, description="更新消息状态")
    updated_by: Optional[str] = Field(None, max_length=255, description="更新者ID")
    update_reason: Optional[str] = Field(None, max_length=500, description="更新原因")


class MessageStatistics(BaseModel):
    """消息统计模型"""
    
    total_messages: int = Field(..., description="消息总数")
    messages_by_type: Dict[str, int] = Field(..., description="按类型分组的消息数")
    messages_by_sender: Dict[str, int] = Field(..., description="按发送者类型分组的消息数")
    messages_by_hour: Dict[str, int] = Field(..., description="按小时分组的消息数")
    messages_by_day: Dict[str, int] = Field(..., description="按日期分组的消息数")
    avg_messages_per_session: float = Field(..., description="每会话平均消息数")
    most_active_users: List[Dict[str, Any]] = Field(..., description="最活跃用户列表")
    peak_hours: List[str] = Field(..., description="消息高峰时段")


class MessageBatchCreate(BaseModel):
    """批量创建消息的请求模型"""
    
    messages: List[MessageCreate] = Field(..., min_items=1, max_items=100, description="消息列表")
    force_creation: bool = Field(False, description="是否强制创建（忽略部分错误）")


class MessageBatchResponse(BaseModel):
    """批量操作响应模型"""
    
    success_count: int = Field(..., description="成功处理的消息数")
    error_count: int = Field(..., description="失败的消息数")
    created_messages: List[MessageRead] = Field(..., description="成功创建的消息列表")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误信息列表")


class MessageAttachment(BaseModel):
    """消息附件模型"""
    
    type: str = Field(..., description="附件类型")
    url: str = Field(..., description="附件URL")
    filename: Optional[str] = Field(None, description="文件名")
    size: Optional[int] = Field(None, ge=0, description="文件大小（字节）")
    mime_type: Optional[str] = Field(None, description="MIME类型")
    thumbnail_url: Optional[str] = Field(None, description="缩略图URL")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附件元数据")


class MessageThread(BaseModel):
    """消息线程模型（用于回复链）"""
    
    root_message: MessageRead = Field(..., description="根消息")
    replies: List[MessageRead] = Field(..., description="回复消息列表")
    reply_count: int = Field(..., description="回复数量")
    last_reply_time: Optional[datetime] = Field(None, description="最后回复时间")
    participants: List[str] = Field(..., description="参与者ID列表")


class MessageExport(BaseModel):
    """消息导出配置模型"""
    
    session_id: Optional[UUID] = Field(None, description="导出指定会话的消息")
    start_time: Optional[datetime] = Field(None, description="导出开始时间")
    end_time: Optional[datetime] = Field(None, description="导出结束时间")
    format: str = Field("json", description="导出格式")
    include_attachments: bool = Field(True, description="是否包含附件")
    include_metadata: bool = Field(True, description="是否包含元数据")
    user_filter: Optional[List[str]] = Field(None, description="用户过滤列表") 