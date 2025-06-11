"""
用户角色管理API端点

提供用户角色分配和权限查询接口
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
from app.services.rbac_service import RBACService
from app.core.permissions import CommonPermissions
from app.schemas.common import StandardResponse, PaginatedResponse

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/rbac", tags=["用户角色管理"])


# 用户角色管理端点
@router.post("/users/{user_id}/roles/{role_id}", response_model=StandardResponse)
async def assign_role_to_user(
    user_id: str,
    role_id: UUID,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.role_assign)
):
    """
    为用户分配角色
    
    需要角色分配权限
    """
    try:
        rbac_service = RBACService(db)
        success = await rbac_service.assign_role_to_user(
            user_id=user_id,
            role_id=role_id,
            tenant_id=current_tenant.id,
            assigned_by=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="角色分配失败"
            )
        
        logger.info("role_assigned_to_user_success",
                   tenant_id=current_tenant.id,
                   assigner_id=current_user.id,
                   target_user_id=user_id,
                   role_id=role_id)
        
        return StandardResponse(
            success=True,
            message="角色分配成功",
            data={
                "user_id": user_id,
                "role_id": str(role_id),
                "assigned_by": current_user.id,
                "assigned_at": "now"
            }
        )
        
    except ValueError as e:
        logger.warning("assign_role_validation_error",
                      tenant_id=current_tenant.id,
                      user_id=user_id,
                      role_id=role_id,
                      error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("assign_role_to_user_error",
                    tenant_id=current_tenant.id,
                    user_id=user_id,
                    role_id=role_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="角色分配失败"
        )


@router.delete("/users/{user_id}/roles/{role_id}", response_model=StandardResponse)
async def remove_role_from_user(
    user_id: str,
    role_id: UUID,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.role_assign)
):
    """
    从用户移除角色
    
    需要角色分配权限
    """
    try:
        rbac_service = RBACService(db)
        success = await rbac_service.remove_role_from_user(
            user_id=user_id,
            role_id=role_id,
            tenant_id=current_tenant.id
        )
        
        if not success:
            logger.warning("role_not_assigned_to_user",
                          tenant_id=current_tenant.id,
                          user_id=user_id,
                          role_id=role_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户未分配此角色"
            )
        
        logger.info("role_removed_from_user_success",
                   tenant_id=current_tenant.id,
                   remover_id=current_user.id,
                   target_user_id=user_id,
                   role_id=role_id)
        
        return StandardResponse(
            success=True,
            message="角色移除成功",
            data={
                "user_id": user_id,
                "role_id": str(role_id),
                "removed_by": current_user.id,
                "removed_at": "now"
            }
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("remove_role_validation_error",
                      tenant_id=current_tenant.id,
                      user_id=user_id,
                      role_id=role_id,
                      error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("remove_role_from_user_error",
                    tenant_id=current_tenant.id,
                    user_id=user_id,
                    role_id=role_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="角色移除失败"
        )


@router.get("/users/{user_id}/permissions", response_model=StandardResponse)
async def get_user_permissions(
    user_id: str,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(CommonPermissions.user_read)
):
    """
    获取用户权限列表
    
    需要用户读权限
    """
    try:
        rbac_service = RBACService(db)
        user = await rbac_service._get_user_with_roles(user_id, current_tenant.id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        permissions = user.get_all_permissions()
        roles = user.get_roles_list()
        
        logger.info("user_permissions_retrieved_success",
                   tenant_id=current_tenant.id,
                   requester_id=current_user.id,
                   target_user_id=user_id,
                   permissions_count=len(permissions))
        
        return StandardResponse(
            success=True,
            message="用户权限获取成功",
            data={
                "user_id": user_id,
                "roles": roles,
                "permissions": permissions,
                "summary": {
                    "roles_count": len(roles),
                    "permissions_count": len(permissions)
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_user_permissions_error",
                    tenant_id=current_tenant.id,
                    user_id=user_id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户权限失败"
        )


@router.get("/check-permission", response_model=StandardResponse)
async def check_permission(
    resource: str = Query(..., description="资源类型"),
    action: str = Query(..., description="操作类型"),
    target_user_id: Optional[str] = Query(None, description="目标用户ID，为空则检查当前用户"),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    检查权限
    
    如果指定target_user_id，需要用户读权限；否则检查当前用户权限
    """
    try:
        rbac_service = RBACService(db)
        
        # 确定要检查的用户
        check_user_id = target_user_id or current_user.id
        
        # 如果检查其他用户权限，需要用户读权限
        if target_user_id and target_user_id != current_user.id:
            has_user_read = await rbac_service.check_user_permission(
                user_id=current_user.id,
                tenant_id=current_tenant.id,
                resource="user",
                action="read"
            )
            if not has_user_read:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权限检查其他用户权限"
                )
        
        # 执行权限检查
        has_permission = await rbac_service.check_user_permission(
            user_id=check_user_id,
            tenant_id=current_tenant.id,
            resource=resource,
            action=action
        )
        
        logger.info("permission_check_completed",
                   tenant_id=current_tenant.id,
                   checker_id=current_user.id,
                   target_user_id=check_user_id,
                   resource=resource,
                   action=action,
                   result=has_permission)
        
        return StandardResponse(
            success=True,
            message="权限检查完成",
            data={
                "user_id": check_user_id,
                "resource": resource,
                "action": action,
                "has_permission": has_permission,
                "permission_key": f"{resource}:{action}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("check_permission_error",
                    tenant_id=current_tenant.id,
                    user_id=current_user.id,
                    resource=resource,
                    action=action,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="权限检查失败"
        ) 