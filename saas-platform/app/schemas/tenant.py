"""
租户Pydantic模式定义
用于API请求验证和响应序列化
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.tenant import TenantStatus, TenantPlan


class TenantBase(BaseModel):
    """租户基础模式"""
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="租户名称",
        examples=["AI客服公司A"]
    )
    email: EmailStr = Field(
        ..., 
        description="管理员邮箱",
        examples=["admin@company-a.com"]
    )
    plan: TenantPlan = Field(
        default=TenantPlan.BASIC,
        description="租户套餐类型"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="扩展元数据"
    )


class TenantCreate(TenantBase):
    """创建租户请求模式"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "AI客服公司A",
                "email": "admin@company-a.com", 
                "plan": "basic",
                "metadata": {
                    "industry": "电商",
                    "company_size": "50-100人"
                }
            }
        }
    )


class TenantUpdate(BaseModel):
    """更新租户请求模式"""
    name: Optional[str] = Field(
        None, 
        min_length=1, 
        max_length=100,
        description="租户名称"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="管理员邮箱"
    )
    plan: Optional[TenantPlan] = Field(
        None,
        description="租户套餐类型"
    )
    status: Optional[TenantStatus] = Field(
        None,
        description="租户状态"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="扩展元数据"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "AI客服公司A（新名称）",
                "plan": "pro",
                "metadata": {
                    "industry": "零售",
                    "company_size": "100-200人"
                }
            }
        }
    )


class TenantRead(TenantBase):
    """租户响应模式（基础版本，不包含敏感信息）"""
    id: UUID = Field(..., description="租户唯一标识")
    status: TenantStatus = Field(..., description="租户状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
    
    # 计算属性
    is_active: bool = Field(..., description="是否处于活跃状态")
    display_name: str = Field(..., description="显示名称")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "AI客服公司A",
                "email": "admin@company-a.com",
                "status": "active",
                "plan": "basic",
                "metadata": {
                    "industry": "电商"
                },
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z",
                "is_active": True,
                "display_name": "AI客服公司A"
            }
        }
    )


class TenantReadWithAPIKey(TenantRead):
    """租户响应模式（包含API密钥，仅限管理员）"""
    api_key: Optional[str] = Field(
        None, 
        description="API访问密钥",
        examples=["ak_live_xxx..."]
    )


class TenantListResponse(BaseModel):
    """租户列表响应模式"""
    items: list[TenantRead] = Field(..., description="租户列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    size: int = Field(..., description="每页大小")
    pages: int = Field(..., description="总页数")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "AI客服公司A",
                        "email": "admin@company-a.com",
                        "status": "active",
                        "plan": "basic",
                        "metadata": {},
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-01T10:00:00Z",
                        "is_active": True,
                        "display_name": "AI客服公司A"
                    }
                ],
                "total": 1,
                "page": 1,
                "size": 10,
                "pages": 1
            }
        }
    )


class TenantStatusUpdate(BaseModel):
    """租户状态更新模式"""
    status: TenantStatus = Field(..., description="新状态")
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="状态变更原因"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "suspended",
                "reason": "账户欠费暂停服务"
            }
        }
    )


class TenantStats(BaseModel):
    """租户统计信息"""
    session_count_today: int = Field(..., description="今日会话数")
    session_count_month: int = Field(..., description="本月会话数")
    message_count_today: int = Field(..., description="今日消息数")
    message_count_month: int = Field(..., description="本月消息数")
    token_usage_month: int = Field(..., description="本月Token使用量")
    active_users_today: int = Field(..., description="今日活跃用户数")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_count_today": 45,
                "session_count_month": 1250,
                "message_count_today": 320,
                "message_count_month": 8750,
                "token_usage_month": 125000,
                "active_users_today": 28
            }
        }
    )


class APIKeyRegenerate(BaseModel):
    """API密钥重新生成请求"""
    confirm: bool = Field(
        ..., 
        description="确认重新生成（旧密钥将失效）"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "confirm": True
            }
        }
    )


class APIKeyResponse(BaseModel):
    """API密钥响应"""
    api_key: str = Field(..., description="新的API密钥")
    created_at: datetime = Field(..., description="生成时间")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "api_key": "ak_live_xyz123...",
                "created_at": "2024-01-01T10:00:00Z"
            }
        }
    ) 