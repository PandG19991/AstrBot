"""
租户管理API端点
提供租户的CRUD操作接口，支持多租户隔离和权限控制
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_tenant,
    get_admin_user,
    get_db_session
)
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from app.schemas.common import StandardResponse, PaginatedResponse
from app.services.tenant_service import TenantService, get_tenant_service
from app.utils.logging import get_logger

# 创建路由器
router = APIRouter(prefix="/tenants", tags=["租户管理"])
logger = get_logger(__name__)


@router.post(
    "",
    response_model=StandardResponse[TenantRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建租户",
    description="创建新的租户，支持企业注册流程"
)
async def create_tenant(
    tenant_data: TenantCreate,
    tenant_service: TenantService = Depends(get_tenant_service)
) -> StandardResponse[TenantRead]:
    """
    创建新租户
    
    - **name**: 企业名称（必须唯一）
    - **contact_email**: 联系邮箱（必须唯一）
    - **display_name**: 显示名称
    - **contact_phone**: 联系电话
    - **description**: 企业描述
    - **industry**: 行业类型
    - **company_size**: 企业规模
    - **subscription_plan**: 订阅计划
    """
    try:
        logger.info(
            "开始创建租户",
            tenant_name=tenant_data.name,
            contact_email=tenant_data.contact_email
        )
        
        # 创建租户
        new_tenant = await tenant_service.create_tenant(tenant_data)
        
        logger.info(
            "租户创建成功",
            tenant_id=str(new_tenant.id),
            tenant_name=new_tenant.name
        )
        
        return StandardResponse(
            success=True,
            message="租户创建成功",
            data=new_tenant
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "租户创建异常",
            error=str(e),
            tenant_data=tenant_data.model_dump()
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="租户创建失败，请稍后重试"
        )


@router.get(
    "/{tenant_id}",
    response_model=StandardResponse[TenantRead],
    summary="获取租户详情",
    description="根据租户ID获取租户详细信息，支持租户隔离"
)
async def get_tenant(
    tenant_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
) -> StandardResponse[TenantRead]:
    """
    获取租户详情
    
    - **tenant_id**: 租户唯一标识
    
    注意：用户只能访问自己所属租户的信息
    """
    try:
        # 租户隔离检查：用户只能访问自己的租户信息
        if current_tenant.id != tenant_id:
            logger.warning(
                "租户访问权限被拒绝",
                current_tenant_id=str(current_tenant.id),
                requested_tenant_id=str(tenant_id)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限访问该租户信息"
            )
        
        # 获取租户信息
        tenant = await tenant_service.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        
        logger.info(
            "租户信息获取成功",
            tenant_id=str(tenant_id),
            current_user_tenant=str(current_tenant.id)
        )
        
        return StandardResponse(
            success=True,
            message="获取租户信息成功",
            data=tenant
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "获取租户信息异常",
            tenant_id=str(tenant_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取租户信息失败"
        )


@router.put(
    "/{tenant_id}",
    response_model=StandardResponse[TenantRead],
    summary="更新租户信息",
    description="更新租户基本信息，支持部分字段更新"
)
async def update_tenant(
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
) -> StandardResponse[TenantRead]:
    """
    更新租户信息
    
    - **tenant_id**: 租户唯一标识
    - 支持部分字段更新，未提供的字段保持不变
    
    注意：用户只能更新自己所属租户的信息
    """
    try:
        # 租户隔离检查
        if current_tenant.id != tenant_id:
            logger.warning(
                "租户更新权限被拒绝",
                current_tenant_id=str(current_tenant.id),
                requested_tenant_id=str(tenant_id)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限更新该租户信息"
            )
        
        # 更新租户信息
        updated_tenant = await tenant_service.update_tenant(tenant_id, tenant_data)
        
        logger.info(
            "租户信息更新成功",
            tenant_id=str(tenant_id),
            updated_fields=list(tenant_data.model_dump(exclude_unset=True).keys())
        )
        
        return StandardResponse(
            success=True,
            message="租户信息更新成功",
            data=updated_tenant
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "更新租户信息异常",
            tenant_id=str(tenant_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新租户信息失败"
        )


@router.delete(
    "/{tenant_id}",
    response_model=StandardResponse[bool],
    summary="删除租户",
    description="软删除租户，支持数据恢复"
)
async def delete_tenant(
    tenant_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
) -> StandardResponse[bool]:
    """
    删除租户（软删除）
    
    - **tenant_id**: 租户唯一标识
    - 执行软删除，数据保留但标记为已删除
    
    注意：用户只能删除自己所属的租户
    """
    try:
        # 租户隔离检查
        if current_tenant.id != tenant_id:
            logger.warning(
                "租户删除权限被拒绝",
                current_tenant_id=str(current_tenant.id),
                requested_tenant_id=str(tenant_id)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限删除该租户"
            )
        
        # 删除租户
        success = await tenant_service.delete_tenant(tenant_id)
        
        if success:
            logger.info(
                "租户删除成功",
                tenant_id=str(tenant_id)
            )
            return StandardResponse(
                success=True,
                message="租户删除成功",
                data=True
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在或已被删除"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "删除租户异常",
            tenant_id=str(tenant_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除租户失败"
        )


@router.get(
    "",
    response_model=PaginatedResponse[TenantRead],
    summary="获取租户列表",
    description="分页获取租户列表，支持搜索和过滤（管理员专用）"
)
async def list_tenants(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="每页记录数"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    current_user: User = Depends(get_admin_user),  # 管理员权限
    tenant_service: TenantService = Depends(get_tenant_service)
) -> PaginatedResponse[TenantRead]:
    """
    获取租户列表（管理员专用）
    
    - **skip**: 跳过的记录数（分页）
    - **limit**: 每页记录数（1-100）
    - **search**: 搜索关键词（按名称或邮箱）
    - **is_active**: 筛选激活状态
    
    注意：此接口仅管理员可访问
    """
    try:
        logger.info(
            "管理员获取租户列表",
            admin_user_id=str(current_user.id),
            skip=skip,
            limit=limit,
            search=search,
            is_active=is_active
        )
        
        # 获取租户列表
        tenants = await tenant_service.list_tenants(
            skip=skip,
            limit=limit,
            search=search,
            is_active=is_active
        )
        
        # 获取总数（简化版本，实际应该优化查询）
        total = len(tenants) + skip  # 简化版本，实际需要单独查询总数
        
        logger.info(
            "租户列表获取成功",
            admin_user_id=str(current_user.id),
            returned_count=len(tenants)
        )
        
        return PaginatedResponse(
            success=True,
            message="获取租户列表成功",
            data=tenants,
            total=total,
            skip=skip,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "获取租户列表异常",
            admin_user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取租户列表失败"
        )


@router.get(
    "/{tenant_id}/stats",
    response_model=StandardResponse[dict],
    summary="获取租户统计信息",
    description="获取租户的统计数据，包括用户数、会话数等"
)
async def get_tenant_statistics(
    tenant_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    tenant_service: TenantService = Depends(get_tenant_service)
) -> StandardResponse[dict]:
    """
    获取租户统计信息
    
    - **tenant_id**: 租户唯一标识
    
    返回统计数据：
    - 用户数量
    - 会话数量  
    - 消息数量
    - 其他业务指标
    
    注意：用户只能查看自己租户的统计信息
    """
    try:
        # 租户隔离检查
        if current_tenant.id != tenant_id:
            logger.warning(
                "租户统计信息访问权限被拒绝",
                current_tenant_id=str(current_tenant.id),
                requested_tenant_id=str(tenant_id)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限访问该租户统计信息"
            )
        
        # 获取统计信息
        stats = await tenant_service.get_tenant_statistics(tenant_id)
        
        logger.info(
            "租户统计信息获取成功",
            tenant_id=str(tenant_id)
        )
        
        return StandardResponse(
            success=True,
            message="获取租户统计信息成功",
            data=stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "获取租户统计信息异常",
            tenant_id=str(tenant_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取租户统计信息失败"
        ) 