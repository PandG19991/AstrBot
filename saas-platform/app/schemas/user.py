"""
用户Pydantic模式定义
用于API请求验证和响应序列化
"""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, validator


class UserBase(BaseModel):
    """用户基础模式"""
    platform: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="来源平台类型",
        examples=["qq_official", "wechat", "telegram"]
    )
    user_id: str = Field(
        ..., 
        min_length=1, 
        max_length=200,
        description="平台内用户ID",
        examples=["123456789", "user_abc123"]
    )
    nickname: Optional[str] = Field(
        None, 
        max_length=100,
        description="用户昵称",
        examples=["小明", "Alice"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="平台特定的扩展数据"
    )


class UserCreate(UserBase):
    """创建用户请求模式"""
    tenant_id: UUID = Field(..., description="所属租户ID")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "platform": "qq_official",
                "user_id": "123456789",
                "nickname": "小明",
                "metadata": {
                    "avatar_url": "https://example.com/avatar.jpg",
                    "join_date": "2024-01-01"
                }
            }
        }
    )


class UserUpdate(BaseModel):
    """更新用户请求模式"""
    nickname: Optional[str] = Field(
        None, 
        max_length=100,
        description="用户昵称"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="平台特定的扩展数据"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nickname": "小明（更新）",
                "metadata": {
                    "last_active": "2024-01-15T10:30:00Z",
                    "status": "active"
                }
            }
        }
    )


class UserRead(UserBase):
    """用户响应模式"""
    id: str = Field(..., description="用户唯一标识 (format: platform:user_id)")
    tenant_id: UUID = Field(..., description="所属租户ID")
    display_name: str = Field(..., description="显示名称")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "qq_official:123456789",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "platform": "qq_official",
                "user_id": "123456789",
                "nickname": "小明",
                "display_name": "小明",
                "metadata": {
                    "avatar_url": "https://example.com/avatar.jpg"
                },
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z"
            }
        }
    )


class UserListResponse(BaseModel):
    """用户列表响应模式"""
    items: list[UserRead] = Field(..., description="用户列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    size: int = Field(..., description="每页大小")
    pages: int = Field(..., description="总页数")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "qq_official:123456789",
                        "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                        "platform": "qq_official",
                        "user_id": "123456789",
                        "nickname": "小明",
                        "display_name": "小明",
                        "metadata": {},
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-01T10:00:00Z"
                    }
                ],
                "total": 1,
                "page": 1,
                "size": 10,
                "pages": 1
            }
        }
    )


class UserSearch(BaseModel):
    """用户搜索请求模式"""
    platform: Optional[str] = Field(
        None, 
        description="按平台筛选"
    )
    keyword: Optional[str] = Field(
        None, 
        min_length=1,
        max_length=100,
        description="搜索关键词（用户ID或昵称）"
    )
    created_after: Optional[datetime] = Field(
        None,
        description="创建时间起始过滤"
    )
    created_before: Optional[datetime] = Field(
        None,
        description="创建时间结束过滤"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "platform": "qq_official",
                "keyword": "小明",
                "created_after": "2024-01-01T00:00:00Z",
                "created_before": "2024-01-31T23:59:59Z"
            }
        }
    )


class PlatformUserInfo(BaseModel):
    """平台用户信息模式"""
    platform: str = Field(..., description="平台类型")
    user_id: str = Field(..., description="平台用户ID")
    composite_id: str = Field(..., description="复合用户ID")
    
    @validator('composite_id', pre=True, always=True)
    def generate_composite_id(cls, v, values):
        """自动生成复合用户ID"""
        if not v and 'platform' in values and 'user_id' in values:
            return f"{values['platform']}:{values['user_id']}"
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "platform": "qq_official",
                "user_id": "123456789",
                "composite_id": "qq_official:123456789"
            }
        }
    )


class UserStats(BaseModel):
    """用户统计信息"""
    total_users: int = Field(..., description="总用户数")
    active_users_today: int = Field(..., description="今日活跃用户")
    new_users_today: int = Field(..., description="今日新增用户")
    users_by_platform: Dict[str, int] = Field(..., description="各平台用户分布")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_users": 1250,
                "active_users_today": 45,
                "new_users_today": 12,
                "users_by_platform": {
                    "qq_official": 800,
                    "wechat": 350,
                    "telegram": 100
                }
            }
        }
    )


class UserBatchCreate(BaseModel):
    """批量创建用户请求模式"""
    users: list[UserCreate] = Field(
        ..., 
        min_items=1,
        max_items=100,
        description="用户列表（最多100个）"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "users": [
                    {
                        "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                        "platform": "qq_official",
                        "user_id": "123456789",
                        "nickname": "用户1"
                    },
                    {
                        "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                        "platform": "wechat",
                        "user_id": "user_abc123",
                        "nickname": "用户2"
                    }
                ]
            }
        }
    )


class UserBatchCreateResponse(BaseModel):
    """批量创建用户响应模式"""
    created: list[UserRead] = Field(..., description="成功创建的用户")
    failed: list[dict] = Field(..., description="创建失败的用户及错误信息")
    summary: dict = Field(..., description="创建汇总")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "created": [
                    {
                        "id": "qq_official:123456789",
                        "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                        "platform": "qq_official",
                        "user_id": "123456789",
                        "nickname": "用户1",
                        "display_name": "用户1",
                        "metadata": {},
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-01T10:00:00Z"
                    }
                ],
                "failed": [
                    {
                        "user_data": {
                            "platform": "wechat",
                            "user_id": "duplicate_user"
                        },
                        "error": "User already exists"
                    }
                ],
                "summary": {
                    "total": 2,
                    "created": 1,
                    "failed": 1
                }
            }
        }
    ) 