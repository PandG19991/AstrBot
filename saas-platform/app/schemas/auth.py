"""
认证相关的Pydantic模式定义
用于登录、注册、Token管理等API的数据验证
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, ConfigDict, validator


class LoginRequest(BaseModel):
    """登录请求模式"""
    email: EmailStr = Field(..., description="用户邮箱")
    password: str = Field(
        ..., 
        min_length=6, 
        max_length=128,
        description="密码"
    )
    remember_me: bool = Field(
        default=False,
        description="记住我（延长Token有效期）"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "password123",
                "remember_me": False
            }
        }
    )


class LoginResponse(BaseModel):
    """登录响应模式"""
    access_token: str = Field(..., description="访问Token")
    refresh_token: str = Field(..., description="刷新Token")
    token_type: str = Field(default="bearer", description="Token类型")
    expires_in: int = Field(..., description="Token过期时间（秒）")
    user_id: str = Field(..., description="用户ID")
    tenant_id: UUID = Field(..., description="租户ID")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 28800,
                "user_id": "qq_official:123456789",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )


class RegisterRequest(BaseModel):
    """注册请求模式"""
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(
        ..., 
        min_length=6, 
        max_length=128,
        description="密码"
    )
    confirm_password: str = Field(
        ..., 
        min_length=6, 
        max_length=128,
        description="确认密码"
    )
    tenant_name: str = Field(
        ..., 
        min_length=2, 
        max_length=100,
        description="租户名称（公司/组织名称）"
    )
    full_name: Optional[str] = Field(
        None, 
        max_length=100,
        description="用户全名"
    )
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """验证密码确认"""
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "admin@company.com",
                "password": "securepassword123",
                "confirm_password": "securepassword123",
                "tenant_name": "我的公司",
                "full_name": "张三"
            }
        }
    )


class RegisterResponse(BaseModel):
    """注册响应模式"""
    message: str = Field(..., description="注册结果消息")
    user_id: str = Field(..., description="创建的用户ID")
    tenant_id: UUID = Field(..., description="创建的租户ID")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Registration successful",
                "user_id": "platform:user123",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )


class RefreshTokenRequest(BaseModel):
    """刷新Token请求模式"""
    refresh_token: str = Field(..., description="刷新Token")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    )


class RefreshTokenResponse(BaseModel):
    """刷新Token响应模式"""
    access_token: str = Field(..., description="新的访问Token")
    token_type: str = Field(default="bearer", description="Token类型")
    expires_in: int = Field(..., description="Token过期时间（秒）")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 28800
            }
        }
    )


class ChangePasswordRequest(BaseModel):
    """修改密码请求模式"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(
        ..., 
        min_length=6, 
        max_length=128,
        description="新密码"
    )
    confirm_new_password: str = Field(
        ..., 
        min_length=6, 
        max_length=128,
        description="确认新密码"
    )
    
    @validator('confirm_new_password')
    def passwords_match(cls, v, values):
        """验证新密码确认"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('New passwords do not match')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_password": "oldpassword123",
                "new_password": "newpassword456",
                "confirm_new_password": "newpassword456"
            }
        }
    )


class ResetPasswordRequest(BaseModel):
    """重置密码请求模式"""
    email: EmailStr = Field(..., description="邮箱地址")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com"
            }
        }
    )


class ResetPasswordConfirm(BaseModel):
    """确认重置密码模式"""
    token: str = Field(..., description="重置Token")
    new_password: str = Field(
        ..., 
        min_length=6, 
        max_length=128,
        description="新密码"
    )
    confirm_new_password: str = Field(
        ..., 
        min_length=6, 
        max_length=128,
        description="确认新密码"
    )
    
    @validator('confirm_new_password')
    def passwords_match(cls, v, values):
        """验证新密码确认"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('New passwords do not match')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token": "reset_token_here",
                "new_password": "newpassword123",
                "confirm_new_password": "newpassword123"
            }
        }
    )


class TokenInfo(BaseModel):
    """Token信息模式"""
    user_id: str = Field(..., description="用户ID")
    tenant_id: UUID = Field(..., description="租户ID")
    email: str = Field(..., description="用户邮箱")
    role: str = Field(..., description="用户角色")
    issued_at: datetime = Field(..., description="签发时间")
    expires_at: datetime = Field(..., description="过期时间")
    token_type: str = Field(..., description="Token类型")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "platform:user123",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "role": "user",
                "issued_at": "2024-01-01T10:00:00Z",
                "expires_at": "2024-01-08T10:00:00Z",
                "token_type": "access"
            }
        }
    )


class LogoutRequest(BaseModel):
    """登出请求模式"""
    revoke_all_tokens: bool = Field(
        default=False,
        description="是否撤销所有Token"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "revoke_all_tokens": False
            }
        }
    )


class ApiKeyCreateRequest(BaseModel):
    """API Key创建请求模式"""
    name: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="API Key名称"
    )
    description: Optional[str] = Field(
        None, 
        max_length=500,
        description="API Key描述"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="过期时间（可选）"
    )
    permissions: list[str] = Field(
        default_factory=list,
        description="权限列表"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Webhook API Key",
                "description": "用于接收Webhook通知的API Key",
                "expires_at": "2024-12-31T23:59:59Z",
                "permissions": ["webhook:receive", "messages:read"]
            }
        }
    )


class ApiKeyResponse(BaseModel):
    """API Key响应模式"""
    id: UUID = Field(..., description="API Key ID")
    name: str = Field(..., description="API Key名称")
    key: str = Field(..., description="API Key值（仅创建时返回）")
    description: Optional[str] = Field(None, description="描述")
    created_at: datetime = Field(..., description="创建时间")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")
    is_active: bool = Field(..., description="是否激活")
    permissions: list[str] = Field(..., description="权限列表")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Webhook API Key",
                "key": "ak_live_1234567890abcdef...",
                "description": "用于接收Webhook通知的API Key",
                "created_at": "2024-01-01T10:00:00Z",
                "expires_at": "2024-12-31T23:59:59Z",
                "last_used_at": "2024-01-15T14:30:00Z",
                "is_active": True,
                "permissions": ["webhook:receive", "messages:read"]
            }
        }
    )


class UserProfile(BaseModel):
    """用户档案模式"""
    user_id: str = Field(..., description="用户ID")
    email: str = Field(..., description="邮箱")
    full_name: Optional[str] = Field(None, description="全名")
    tenant_id: UUID = Field(..., description="租户ID")
    tenant_name: str = Field(..., description="租户名称")
    role: str = Field(..., description="用户角色")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    last_login_at: Optional[datetime] = Field(None, description="最后登录时间")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "platform:user123",
                "email": "user@example.com",
                "full_name": "张三",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_name": "我的公司",
                "role": "admin",
                "is_active": True,
                "created_at": "2024-01-01T10:00:00Z",
                "last_login_at": "2024-01-15T09:30:00Z"
            }
        }
    )


class AuthError(BaseModel):
    """认证错误响应模式"""
    detail: str = Field(..., description="错误详情")
    error_code: str = Field(..., description="错误代码")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Invalid credentials",
                "error_code": "INVALID_CREDENTIALS"
            }
        }
    ) 