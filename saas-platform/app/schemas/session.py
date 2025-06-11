"""
会话Pydantic模式定义
用于API请求验证和响应序列化
"""
from datetime import datetime
from typing import Any, Dict, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.models.session import SessionStatus, ChannelType


class SessionBase(BaseModel):
    """会话基础模式"""
    platform: str = Field(..., description="来源平台类型")
    channel_type: ChannelType = Field(
        default=ChannelType.DIRECT,
        description="消息渠道类型"
    )
    priority: int = Field(
        default=5, 
        ge=1, 
        le=10,
        description="会话优先级（1-10）"
    )
    context_summary: Optional[str] = Field(
        None,
        max_length=1000,
        description="会话摘要"
    )


class SessionCreate(SessionBase):
    """创建会话请求模式"""
    user_id: str = Field(..., description="用户ID")
    customer_name: Optional[str] = Field(None, description="客户姓名")
    customer_avatar: Optional[str] = Field(None, description="客户头像")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class SessionRead(SessionBase):
    """会话响应模式"""
    id: UUID = Field(..., description="会话唯一标识")
    tenant_id: UUID = Field(..., description="所属租户ID")
    user_id: str = Field(..., description="用户ID")
    status: SessionStatus = Field(..., description="会话状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class SessionUpdate(BaseModel):
    """更新会话请求模式"""
    status: Optional[SessionStatus] = Field(None, description="会话状态")
    priority: Optional[int] = Field(
        None, 
        ge=1, 
        le=10,
        description="会话优先级"
    )
    context_summary: Optional[str] = Field(
        None,
        max_length=1000,
        description="会话摘要"
    )


class SessionStatusUpdate(BaseModel):
    """会话状态更新模式"""
    status: SessionStatus = Field(..., description="新状态")
    agent_id: Optional[UUID] = Field(None, description="分配的客服ID")
    reason: Optional[str] = Field(None, max_length=200, description="状态变更原因")


class IncomingSessionData(BaseModel):
    """传入会话数据模式"""
    user_id: str = Field(..., description="用户ID")
    platform: str = Field(..., description="来源平台类型")
    customer_name: Optional[str] = Field(None, description="客户姓名")
    customer_avatar: Optional[str] = Field(None, description="客户头像")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="扩展元数据") 