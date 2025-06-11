"""
API依赖注入模块
包含认证、授权和租户隔离相关的依赖
"""
from typing import Optional, Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    verify_token, 
    get_subject_from_token, 
    get_tenant_id_from_token,
    TokenExpiredError, 
    InvalidTokenError,
    extract_token_from_header
)
from app.models.tenant import Tenant
from app.models.user import User


# HTTPBearer安全方案
security = HTTPBearer()


class AuthenticationError(HTTPException):
    """认证异常"""
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    """授权异常"""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class TenantAccessError(HTTPException):
    """租户访问异常"""
    def __init__(self, detail: str = "Tenant access denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


async def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    获取当前请求的JWT Token
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        str: JWT Token
        
    Raises:
        AuthenticationError: Token无效或缺失
    """
    if not credentials:
        raise AuthenticationError("Missing authentication credentials")
    
    token = credentials.credentials
    if not token:
        raise AuthenticationError("Missing token")
    
    return token


async def get_current_user_id(
    token: str = Depends(get_current_token)
) -> str:
    """
    从Token中获取当前用户ID
    
    Args:
        token: JWT Token
        
    Returns:
        str: 用户ID
        
    Raises:
        AuthenticationError: Token无效或过期
    """
    try:
        # 验证Token并获取用户ID
        user_id = get_subject_from_token(token)
        return user_id
        
    except TokenExpiredError:
        raise AuthenticationError("Token has expired")
    except InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise AuthenticationError(f"Authentication failed: {str(e)}")


async def get_current_tenant_id(
    token: str = Depends(get_current_token)
) -> UUID:
    """
    从Token中获取当前租户ID
    
    Args:
        token: JWT Token
        
    Returns:
        UUID: 租户ID
        
    Raises:
        AuthenticationError: Token无效或缺少租户信息
    """
    try:
        # 从Token中提取租户ID
        tenant_id = get_tenant_id_from_token(token)
        
        if not tenant_id:
            raise AuthenticationError("Token missing tenant information")
        
        return tenant_id
        
    except TokenExpiredError:
        raise AuthenticationError("Token has expired")
    except InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise AuthenticationError(f"Failed to extract tenant ID: {str(e)}")


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前认证用户
    
    Args:
        user_id: 用户ID
        tenant_id: 租户ID
        db: 数据库会话
        
    Returns:
        User: 用户对象
        
    Raises:
        AuthenticationError: 用户不存在或不属于当前租户
    """
    try:
        # 查询用户（确保租户隔离）
        user = await db.get(User, user_id)
        
        if not user:
            raise AuthenticationError("User not found")
        
        # 验证用户属于当前租户
        if user.tenant_id != tenant_id:
            raise TenantAccessError("User does not belong to current tenant")
        
        return user
        
    except AuthenticationError:
        raise
    except TenantAccessError:
        raise
    except Exception as e:
        raise AuthenticationError(f"Failed to get current user: {str(e)}")


async def get_current_tenant(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    获取当前租户
    
    Args:
        tenant_id: 租户ID
        db: 数据库会话
        
    Returns:
        Tenant: 租户对象
        
    Raises:
        AuthenticationError: 租户不存在或已停用
    """
    try:
        # 查询租户
        tenant = await db.get(Tenant, tenant_id)
        
        if not tenant:
            raise AuthenticationError("Tenant not found")
        
        # 检查租户状态
        if not tenant.is_active:
            raise AuthenticationError("Tenant is not active")
        
        return tenant
        
    except AuthenticationError:
        raise
    except Exception as e:
        raise AuthenticationError(f"Failed to get current tenant: {str(e)}")


async def require_tenant_access(
    resource_tenant_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant)
) -> None:
    """
    验证租户访问权限
    
    用于保护跨租户资源访问
    
    Args:
        resource_tenant_id: 资源所属租户ID
        current_tenant: 当前租户
        
    Raises:
        TenantAccessError: 无权访问其他租户的资源
    """
    if resource_tenant_id != current_tenant.id:
        raise TenantAccessError("Cannot access resources from other tenants")


async def get_optional_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    获取可选的当前用户（用于支持匿名访问的端点）
    
    Args:
        authorization: Authorization头
        db: 数据库会话
        
    Returns:
        Optional[User]: 用户对象，如果未认证则返回None
    """
    if not authorization:
        return None
    
    try:
        # 提取Token
        token = extract_token_from_header(authorization)
        
        # 获取用户和租户ID
        user_id = get_subject_from_token(token)
        tenant_id = get_tenant_id_from_token(token)
        
        if not user_id or not tenant_id:
            return None
        
        # 查询用户
        user = await db.get(User, user_id)
        if user and user.tenant_id == tenant_id:
            return user
        
        return None
        
    except (TokenExpiredError, InvalidTokenError):
        return None
    except Exception:
        return None


def require_role(required_role: str):
    """
    角色权限装饰器工厂
    
    Args:
        required_role: 必需的角色
        
    Returns:
        依赖函数
    """
    async def check_role(
        token: str = Depends(get_current_token)
    ) -> None:
        try:
            payload = verify_token(token)
            user_role = payload.get("role", "user")
            
            # 简单的角色检查（实际项目中可能需要更复杂的权限系统）
            role_hierarchy = {
                "user": 1,
                "staff": 2,
                "admin": 3,
                "super_admin": 4
            }
            
            required_level = role_hierarchy.get(required_role, 0)
            user_level = role_hierarchy.get(user_role, 0)
            
            if user_level < required_level:
                raise AuthorizationError(f"Requires {required_role} role or higher")
                
        except (TokenExpiredError, InvalidTokenError):
            raise AuthenticationError("Invalid or expired token")
        except AuthorizationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Role verification failed: {str(e)}")
    
    return check_role


# 常用角色依赖
require_staff_role = require_role("staff")
require_admin_role = require_role("admin")
require_super_admin_role = require_role("super_admin")


async def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    API Key认证依赖
    
    用于Webhook和第三方API调用
    
    Args:
        x_api_key: API Key
        db: 数据库会话
        
    Returns:
        Tenant: API Key对应的租户
        
    Raises:
        AuthenticationError: API Key无效
    """
    if not x_api_key:
        raise AuthenticationError("Missing API key")
    
    try:
        # 从数据库查找API Key对应的租户
        from sqlalchemy import select
        
        stmt = select(Tenant).where(Tenant.api_key == x_api_key)
        result = await db.execute(stmt)
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise AuthenticationError("Invalid API key")
        
        if not tenant.is_active:
            raise AuthenticationError("Tenant is not active")
        
        return tenant
        
    except AuthenticationError:
        raise
    except Exception as e:
        raise AuthenticationError(f"API key verification failed: {str(e)}")


class TenantContext:
    """租户上下文管理器"""
    
    def __init__(self):
        self._current_tenant_id: Optional[UUID] = None
    
    def set_tenant_id(self, tenant_id: UUID) -> None:
        """设置当前租户ID"""
        self._current_tenant_id = tenant_id
    
    def get_tenant_id(self) -> Optional[UUID]:
        """获取当前租户ID"""
        return self._current_tenant_id
    
    def clear(self) -> None:
        """清理租户上下文"""
        self._current_tenant_id = None


# 全局租户上下文实例
tenant_context = TenantContext()


async def set_tenant_context(
    tenant: Tenant = Depends(get_current_tenant)
) -> None:
    """
    设置租户上下文（用于中间件或特殊场景）
    
    Args:
        tenant: 当前租户
    """
    tenant_context.set_tenant_id(tenant.id)


def get_tenant_context() -> Optional[UUID]:
    """
    获取当前租户上下文
    
    Returns:
        Optional[UUID]: 当前租户ID
    """
    return tenant_context.get_tenant_id()


async def validate_tenant_resource_access(
    resource_tenant_id: UUID,
    current_tenant_id: UUID = Depends(get_current_tenant_id)
) -> None:
    """
    验证租户资源访问权限的快捷依赖
    
    Args:
        resource_tenant_id: 资源所属租户ID
        current_tenant_id: 当前租户ID
        
    Raises:
        TenantAccessError: 跨租户访问被拒绝
    """
    if resource_tenant_id != current_tenant_id:
        raise TenantAccessError(
            "Access denied: Cannot access resources from other tenants"
        )


async def get_current_tenant_from_token(
    token: str,
    db: AsyncSession
) -> Optional[Tenant]:
    """
    直接从Token获取租户信息（用于WebSocket等场景）
    
    Args:
        token: JWT Token字符串
        db: 数据库会话
        
    Returns:
        Optional[Tenant]: 租户对象，验证失败返回None
    """
    try:
        # 验证Token并获取租户ID
        tenant_id = get_tenant_id_from_token(token)
        
        if not tenant_id:
            return None
        
        # 查询租户
        tenant = await db.get(Tenant, tenant_id)
        
        if not tenant:
            return None
        
        # 检查租户状态
        if tenant.status != "active":
            return None
        
        return tenant
        
    except (TokenExpiredError, InvalidTokenError):
        return None
    except Exception:
        return None 