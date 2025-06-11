"""
权限检查装饰器和中间件

提供API权限验证功能
"""
import logging
from functools import wraps
from typing import List, Optional, Callable, Any

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_tenant
from app.models.user import User
from app.models.tenant import Tenant
from app.services.rbac_service import RBACService

# 配置日志
logger = logging.getLogger(__name__)

# HTTP Bearer认证
security = HTTPBearer()


class PermissionError(HTTPException):
    """权限错误异常"""
    
    def __init__(
        self,
        detail: str = "Permission denied",
        resource: Optional[str] = None,
        action: Optional[str] = None
    ):
        """
        初始化权限错误
        
        Args:
            detail: 错误详情
            resource: 资源类型
            action: 操作类型
        """
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )
        self.resource = resource
        self.action = action
        
        # 记录权限拒绝日志
        logger.warning("permission_denied",
                      detail=detail,
                      resource=resource,
                      action=action)


def require_permission(resource: str, action: str):
    """
    权限检查装饰器
    
    Args:
        resource: 所需资源权限
        action: 所需操作权限
        
    Returns:
        装饰器函数
        
    Usage:
        @require_permission("session", "read")
        async def get_sessions(...):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取依赖注入的参数
            current_user = kwargs.get('current_user')
            current_tenant = kwargs.get('current_tenant')
            db = kwargs.get('db')
            
            # 如果没有通过依赖注入获取，尝试从args中获取
            if not current_user or not current_tenant or not db:
                # 这种情况下需要在路由中正确使用依赖注入
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission check setup error"
                )
            
            # 检查权限
            rbac_service = RBACService(db)
            has_permission = await rbac_service.check_user_permission(
                user_id=current_user.id,
                tenant_id=current_tenant.id,
                resource=resource,
                action=action
            )
            
            if not has_permission:
                logger.warning("permission_check_failed",
                              user_id=current_user.id,
                              tenant_id=current_tenant.id,
                              resource=resource,
                              action=action)
                raise PermissionError(
                    detail=f"Permission denied: {resource}:{action}",
                    resource=resource,
                    action=action
                )
            
            # 记录权限检查成功
            logger.debug("permission_check_passed",
                        user_id=current_user.id,
                        tenant_id=current_tenant.id,
                        resource=resource,
                        action=action)
            
            # 调用原函数
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class PermissionChecker:
    """权限检查器类"""
    
    def __init__(self, resource: str, action: str):
        """
        初始化权限检查器
        
        Args:
            resource: 资源类型
            action: 操作类型
        """
        self.resource = resource
        self.action = action
    
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        current_tenant: Tenant = Depends(get_current_tenant),
        db: AsyncSession = Depends(get_db)
    ) -> bool:
        """
        执行权限检查
        
        Args:
            current_user: 当前用户
            current_tenant: 当前租户
            db: 数据库会话
            
        Returns:
            bool: 是否有权限
            
        Raises:
            PermissionError: 权限不足时抛出
        """
        rbac_service = RBACService(db)
        
        has_permission = await rbac_service.check_user_permission(
            user_id=current_user.id,
            tenant_id=current_tenant.id,
            resource=self.resource,
            action=self.action
        )
        
        if not has_permission:
            logger.warning("permission_check_failed",
                          user_id=current_user.id,
                          tenant_id=current_tenant.id,
                          resource=self.resource,
                          action=self.action)
            raise PermissionError(
                detail=f"Permission denied: {self.resource}:{self.action}",
                resource=self.resource,
                action=self.action
            )
        
        logger.debug("permission_check_passed",
                    user_id=current_user.id,
                    tenant_id=current_tenant.id,
                    resource=self.resource,
                    action=self.action)
        
        return True


def require_any_permission(permissions: List[tuple[str, str]]):
    """
    需要任意一个权限的装饰器
    
    Args:
        permissions: 权限列表，每个权限为(resource, action)元组
        
    Returns:
        装饰器函数
        
    Usage:
        @require_any_permission([("session", "read"), ("session", "write")])
        async def manage_session(...):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取依赖注入的参数
            current_user = kwargs.get('current_user')
            current_tenant = kwargs.get('current_tenant')
            db = kwargs.get('db')
            
            if not current_user or not current_tenant or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission check setup error"
                )
            
            # 检查是否有任意一个权限
            rbac_service = RBACService(db)
            has_any_permission = False
            
            for resource, action in permissions:
                if await rbac_service.check_user_permission(
                    user_id=current_user.id,
                    tenant_id=current_tenant.id,
                    resource=resource,
                    action=action
                ):
                    has_any_permission = True
                    logger.debug("permission_check_passed",
                                user_id=current_user.id,
                                tenant_id=current_tenant.id,
                                resource=resource,
                                action=action)
                    break
            
            if not has_any_permission:
                permission_strings = [f"{r}:{a}" for r, a in permissions]
                logger.warning("any_permission_check_failed",
                              user_id=current_user.id,
                              tenant_id=current_tenant.id,
                              required_permissions=permission_strings)
                raise PermissionError(
                    detail=f"Permission denied: one of {permission_strings} required"
                )
            
            # 调用原函数
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_all_permissions(permissions: List[tuple[str, str]]):
    """
    需要所有权限的装饰器
    
    Args:
        permissions: 权限列表，每个权限为(resource, action)元组
        
    Returns:
        装饰器函数
        
    Usage:
        @require_all_permissions([("session", "read"), ("message", "write")])
        async def complex_operation(...):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取依赖注入的参数
            current_user = kwargs.get('current_user')
            current_tenant = kwargs.get('current_tenant')
            db = kwargs.get('db')
            
            if not current_user or not current_tenant or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission check setup error"
                )
            
            # 检查是否有所有权限
            rbac_service = RBACService(db)
            missing_permissions = []
            
            for resource, action in permissions:
                if not await rbac_service.check_user_permission(
                    user_id=current_user.id,
                    tenant_id=current_tenant.id,
                    resource=resource,
                    action=action
                ):
                    missing_permissions.append(f"{resource}:{action}")
            
            if missing_permissions:
                logger.warning("all_permissions_check_failed",
                              user_id=current_user.id,
                              tenant_id=current_tenant.id,
                              missing_permissions=missing_permissions)
                raise PermissionError(
                    detail=f"Permission denied: missing {missing_permissions}"
                )
            
            logger.debug("all_permissions_check_passed",
                        user_id=current_user.id,
                        tenant_id=current_tenant.id,
                        checked_permissions=[f"{r}:{a}" for r, a in permissions])
            
            # 调用原函数
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# 常用权限检查器实例
class CommonPermissions:
    """常用权限检查器"""
    
    # 租户管理权限
    tenant_read = PermissionChecker("tenant", "read")
    tenant_write = PermissionChecker("tenant", "write")
    tenant_delete = PermissionChecker("tenant", "delete")
    
    # 用户管理权限
    user_read = PermissionChecker("user", "read")
    user_write = PermissionChecker("user", "write")
    user_delete = PermissionChecker("user", "delete")
    
    # 会话管理权限
    session_read = PermissionChecker("session", "read")
    session_write = PermissionChecker("session", "write")
    session_delete = PermissionChecker("session", "delete")
    
    # 消息管理权限
    message_read = PermissionChecker("message", "read")
    message_write = PermissionChecker("message", "write")
    message_delete = PermissionChecker("message", "delete")
    
    # 角色管理权限
    role_read = PermissionChecker("role", "read")
    role_write = PermissionChecker("role", "write")
    role_assign = PermissionChecker("role", "assign")
    
    # AI功能权限
    ai_use = PermissionChecker("ai", "use")
    ai_config = PermissionChecker("ai", "config")
    
    # 实例管理权限
    instance_read = PermissionChecker("instance", "read")
    instance_write = PermissionChecker("instance", "write")
    instance_config = PermissionChecker("instance", "config")
    
    # 数据分析权限
    analytics_read = PermissionChecker("analytics", "read")
    analytics_create = PermissionChecker("analytics", "create")
    analytics_export = PermissionChecker("analytics", "export")
    
    # 便捷别名方法
    @staticmethod
    def can_view_analytics():
        """查看分析数据权限"""
        return CommonPermissions.analytics_read
    
    @staticmethod
    def can_create_analytics():
        """创建分析报表权限"""
        return CommonPermissions.analytics_create
    
    @staticmethod
    def can_export_analytics():
        """导出分析数据权限"""
        return CommonPermissions.analytics_export


# 常用权限装饰器
def require_tenant_read(func: Callable) -> Callable:
    """需要租户读权限"""
    return require_permission("tenant", "read")(func)

def require_tenant_write(func: Callable) -> Callable:
    """需要租户写权限"""
    return require_permission("tenant", "write")(func)

def require_session_read(func: Callable) -> Callable:
    """需要会话读权限"""
    return require_permission("session", "read")(func)

def require_session_write(func: Callable) -> Callable:
    """需要会话写权限"""
    return require_permission("session", "write")(func)

def require_message_read(func: Callable) -> Callable:
    """需要消息读权限"""
    return require_permission("message", "read")(func)

def require_message_write(func: Callable) -> Callable:
    """需要消息写权限"""
    return require_permission("message", "write")(func)

def require_role_manage(func: Callable) -> Callable:
    """需要角色管理权限"""
    return require_permission("role", "write")(func)

def require_ai_use(func: Callable) -> Callable:
    """需要AI使用权限"""
    return require_permission("ai", "use")(func)

def require_instance_manage(func: Callable) -> Callable:
    """需要实例管理权限"""
    return require_permission("instance", "write")(func)


async def check_permission_dependency(
    resource: str,
    action: str,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> bool:
    """
    通用权限检查依赖
    
    Args:
        resource: 资源类型
        action: 操作类型
        current_user: 当前用户
        current_tenant: 当前租户
        db: 数据库会话
        
    Returns:
        bool: 是否有权限
        
    Raises:
        PermissionError: 权限不足时抛出
    """
    rbac_service = RBACService(db)
    
    has_permission = await rbac_service.check_user_permission(
        user_id=current_user.id,
        tenant_id=current_tenant.id,
        resource=resource,
        action=action
    )
    
    if not has_permission:
        raise PermissionError(
            detail=f"Permission denied: {resource}:{action}",
            resource=resource,
            action=action
        )
    
    return True 