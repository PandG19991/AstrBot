"""
RBAC权限管理API端点

提供角色和权限的CRUD接口
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_tenant
from app.models.user import User
from app.models.tenant import Tenant
from app.models.role import Role, Permission
from app.services.rbac_service import RBACService
from app.core.permissions import CommonPermissions
from app.schemas.common import StandardResponse, PaginatedResponse

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/rbac", tags=["RBAC权限管理"])


# 权限管理端点
@router.get("/permissions", response_model=StandardResponse)
async def list_permissions(
    resource: Optional[str] = Query(None, description="过滤资源类型"),
    action: Optional[str] = Query(None, description="过滤操作类型"),
    active_only: bool = Query(True, description="只返回激活的权限"),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.role_read)
):
    """
    获取权限列表
    
    需要角色读权限
    """
    try:
        rbac_service = RBACService(db)
        permissions = await rbac_service.list_permissions(
            resource=resource,
            action=action,
            active_only=active_only
        )
        
        permission_data = [
            {
                "id": str(permission.id),
                "name": permission.name,
                "description": permission.description,
                "resource": permission.resource,
                "action": permission.action,
                "is_active": permission.is_active,
                "created_at": permission.created_at.isoformat() if permission.created_at else None
            }
            for permission in permissions
        ]
        
        logger.info("permissions_listed_success",
                   tenant_id=current_tenant.id,
                   user_id=current_user.id,
                   count=len(permission_data),
                   filters={"resource": resource, "action": action, "active_only": active_only})
        
        return StandardResponse(
            success=True,
            message="权限列表获取成功",
            data={
                "permissions": permission_data,
                "total": len(permission_data)
            }
        )
        
    except Exception as e:
        logger.error("list_permissions_error",
                    tenant_id=current_tenant.id,
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取权限列表失败"
        )


@router.post("/permissions/initialize", response_model=StandardResponse)
async def initialize_default_permissions(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.role_write)
):
    """
    初始化默认权限
    
    需要角色管理权限，通常只有系统管理员可以执行
    """
    try:
        rbac_service = RBACService(db)
        permissions = await rbac_service.initialize_default_permissions()
        
        logger.info("default_permissions_initialized",
                   tenant_id=current_tenant.id,
                   user_id=current_user.id,
                   count=len(permissions))
        
        return StandardResponse(
            success=True,
            message="默认权限初始化成功",
            data={
                "initialized_count": len(permissions),
                "permissions": [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "resource": p.resource,
                        "action": p.action
                    }
                    for p in permissions
                ]
            }
        )
        
    except Exception as e:
        logger.error("initialize_default_permissions_error",
                    tenant_id=current_tenant.id,
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="初始化默认权限失败"
        )


# 角色管理端点
@router.post("/roles", response_model=StandardResponse)
async def create_role(
    name: str,
    display_name: str,
    description: Optional[str] = None,
    permission_ids: Optional[List[UUID]] = None,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.role_write)
):
    """
    创建角色
    
    需要角色管理权限
    """
    try:
        rbac_service = RBACService(db)
        role = await rbac_service.create_role(
            tenant_id=current_tenant.id,
            name=name,
            display_name=display_name,
            description=description,
            permission_ids=permission_ids or [],
            is_system_role=False
        )
        
        logger.info("role_created_success",
                   tenant_id=current_tenant.id,
                   user_id=current_user.id,
                   role_id=role.id,
                   role_name=name)
        
        return StandardResponse(
            success=True,
            message="角色创建成功",
            data={
                "role": {
                    "id": str(role.id),
                    "name": role.name,
                    "display_name": role.display_name,
                    "description": role.description,
                    "is_system_role": role.is_system_role,
                    "permissions": role.get_permissions_list(),
                    "created_at": role.created_at.isoformat() if role.created_at else None
                }
            }
        )
        
    except ValueError as e:
        logger.warning("create_role_validation_error",
                      tenant_id=current_tenant.id,
                      user_id=current_user.id,
                      error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("create_role_error",
                    tenant_id=current_tenant.id,
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="角色创建失败"
        )


@router.get("/roles", response_model=StandardResponse)
async def list_roles(
    active_only: bool = Query(True, description="只返回激活的角色"),
    include_system: bool = Query(True, description="是否包含系统角色"),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.role_read)
):
    """
    获取租户角色列表
    
    需要角色读权限
    """
    try:
        rbac_service = RBACService(db)
        roles = await rbac_service.list_roles(
            tenant_id=current_tenant.id,
            active_only=active_only,
            include_system=include_system
        )
        
        role_data = [
            {
                "id": str(role.id),
                "name": role.name,
                "display_name": role.display_name,
                "description": role.description,
                "is_system_role": role.is_system_role,
                "is_active": role.is_active,
                "permissions_count": len(role.permissions),
                "permissions": role.get_permissions_list(),
                "created_at": role.created_at.isoformat() if role.created_at else None
            }
            for role in roles
        ]
        
        logger.info("roles_listed_success",
                   tenant_id=current_tenant.id,
                   user_id=current_user.id,
                   count=len(role_data))
        
        return StandardResponse(
            success=True,
            message="角色列表获取成功",
            data={
                "roles": role_data,
                "total": len(role_data)
            }
        )
        
    except Exception as e:
        logger.error("list_roles_error",
                    tenant_id=current_tenant.id,
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取角色列表失败"
        )


@router.get("/roles/{role_id}", response_model=StandardResponse)
async def get_role(
    role_id: UUID,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.role_read)
):
    """
    获取角色详情
    
    需要角色读权限
    """
    try:
        rbac_service = RBACService(db)
        role = await rbac_service.get_role(role_id, current_tenant.id)
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="角色不存在"
            )
        
        logger.info("role_retrieved_success",
                   tenant_id=current_tenant.id,
                   user_id=current_user.id,
                   role_id=role_id)
        
        return StandardResponse(
            success=True,
            message="角色详情获取成功",
            data={
                "role": {
                    "id": str(role.id),
                    "name": role.name,
                    "display_name": role.display_name,
                    "description": role.description,
                    "is_system_role": role.is_system_role,
                    "is_active": role.is_active,
                    "permissions": role.get_permissions_list(),
                    "created_at": role.created_at.isoformat() if role.created_at else None,
                    "updated_at": role.updated_at.isoformat() if role.updated_at else None
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_role_error",
                    tenant_id=current_tenant.id,
                    user_id=current_user.id,
                    role_id=role_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取角色详情失败"
        )


@router.put("/roles/{role_id}/permissions", response_model=StandardResponse)
async def update_role_permissions(
    role_id: UUID,
    permission_ids: List[UUID],
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.role_write)
):
    """
    更新角色权限
    
    需要角色管理权限
    """
    try:
        rbac_service = RBACService(db)
        role = await rbac_service.update_role_permissions(
            role_id=role_id,
            tenant_id=current_tenant.id,
            permission_ids=permission_ids
        )
        
        logger.info("role_permissions_updated_success",
                   tenant_id=current_tenant.id,
                   user_id=current_user.id,
                   role_id=role_id,
                   permissions_count=len(permission_ids))
        
        return StandardResponse(
            success=True,
            message="角色权限更新成功",
            data={
                "role": {
                    "id": str(role.id),
                    "name": role.name,
                    "display_name": role.display_name,
                    "permissions": role.get_permissions_list(),
                    "updated_at": role.updated_at.isoformat() if role.updated_at else None
                }
            }
        )
        
    except ValueError as e:
        logger.warning("update_role_permissions_validation_error",
                      tenant_id=current_tenant.id,
                      user_id=current_user.id,
                      role_id=role_id,
                      error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("update_role_permissions_error",
                    tenant_id=current_tenant.id,
                    user_id=current_user.id,
                    role_id=role_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新角色权限失败"
        )


# 角色和权限管理完成 - 用户角色管理已迁移到单独文件 