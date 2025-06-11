"""
实例管理API端点

提供AstrBot实例认证、配置管理等功能
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.deps import get_db, get_current_tenant
from app.services.instance_auth_service import InstanceAuthService  
from app.services.instance_config_service import InstanceConfigService
from app.schemas.common import StandardResponse, PaginatedResponse
from app.models.tenant import Tenant

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/instances", tags=["instances"])


# Pydantic模型
class InstanceTokenRequest(BaseModel):
    """生成实例Token请求"""
    instance_id: str = Field(..., description="实例ID")
    instance_name: Optional[str] = Field(None, description="实例名称")
    expires_days: int = Field(365, ge=1, le=3650, description="过期天数(1-3650)")


class InstanceConfigUpdate(BaseModel):
    """实例配置更新请求"""
    config_updates: Dict[str, Any] = Field(..., description="配置更新")
    auto_push: bool = Field(True, description="是否自动推送到实例")


class ConfigPushRequest(BaseModel):
    """配置推送请求"""
    instance_id: str = Field(..., description="实例ID")
    config_data: Dict[str, Any] = Field(..., description="配置数据")
    instance_endpoint: Optional[str] = Field(None, description="实例端点URL")


class ConfigBroadcastRequest(BaseModel):
    """配置广播请求"""
    config_data: Dict[str, Any] = Field(..., description="配置数据")
    instance_filter: Optional[Dict[str, Any]] = Field(None, description="实例过滤条件")


@router.post("/tokens")
async def generate_instance_token(
    request: InstanceTokenRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    为AstrBot实例生成认证Token
    
    Args:
        request: Token生成请求
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: Token信息
    """
    try:
        auth_service = InstanceAuthService(db)
        
        result = await auth_service.generate_instance_token(
            tenant_id=tenant.id,
            instance_id=request.instance_id,
            instance_name=request.instance_name,
            expires_days=request.expires_days
        )
        
        logger.info("instance_token_generated_via_api",
                   tenant_id=tenant.id,
                   instance_id=request.instance_id)
        
        return StandardResponse(
            data=result,
            message="Instance token generated successfully"
        )
        
    except ValueError as e:
        logger.error("generate_instance_token_validation_error",
                    tenant_id=tenant.id,
                    instance_id=request.instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
    except Exception as e:
        logger.error("generate_instance_token_error",
                    tenant_id=tenant.id,
                    instance_id=request.instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to generate instance token"
        )


@router.get("/tokens")
async def list_instance_tokens(
    include_revoked: bool = Query(False, description="是否包含已撤销的Token"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    列出租户的所有实例Token
    
    Args:
        include_revoked: 是否包含已撤销的Token
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: Token列表
    """
    try:
        auth_service = InstanceAuthService(db)
        
        tokens = await auth_service.list_instance_tokens(
            tenant_id=tenant.id,
            include_revoked=include_revoked
        )
        
        return StandardResponse(
            data={
                "tokens": tokens,
                "total_count": len(tokens),
                "include_revoked": include_revoked
            },
            message="Instance tokens retrieved successfully"
        )
        
    except Exception as e:
        logger.error("list_instance_tokens_error",
                    tenant_id=tenant.id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to list instance tokens"
        )


@router.delete("/tokens/{instance_id}")
async def revoke_instance_token(
    instance_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    撤销实例Token
    
    Args:
        instance_id: 实例ID
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 撤销结果
    """
    try:
        auth_service = InstanceAuthService(db)
        
        result = await auth_service.revoke_instance_token(
            tenant_id=tenant.id,
            instance_id=instance_id
        )
        
        logger.info("instance_token_revoked_via_api",
                   tenant_id=tenant.id,
                   instance_id=instance_id)
        
        return StandardResponse(
            data=result,
            message="Instance token revoked successfully"
        )
        
    except ValueError as e:
        logger.error("revoke_instance_token_validation_error",
                    tenant_id=tenant.id,
                    instance_id=instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    
    except Exception as e:
        logger.error("revoke_instance_token_error",
                    tenant_id=tenant.id,
                    instance_id=instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke instance token"
        )


@router.post("/tokens/{instance_id}/rotate")
async def rotate_instance_token(
    instance_id: str,
    expires_days: int = Query(365, ge=1, le=3650, description="新Token过期天数"),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    轮换实例Token
    
    Args:
        instance_id: 实例ID
        expires_days: 新Token过期天数
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 新Token信息
    """
    try:
        auth_service = InstanceAuthService(db)
        
        result = await auth_service.rotate_instance_token(
            tenant_id=tenant.id,
            instance_id=instance_id,
            expires_days=expires_days
        )
        
        logger.info("instance_token_rotated_via_api",
                   tenant_id=tenant.id,
                   instance_id=instance_id)
        
        return StandardResponse(
            data=result,
            message="Instance token rotated successfully"
        )
        
    except Exception as e:
        logger.error("rotate_instance_token_error",
                    tenant_id=tenant.id,
                    instance_id=instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to rotate instance token"
        )


@router.get("/tokens/{instance_id}/credentials")
async def get_instance_credentials(
    instance_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    获取实例认证凭据信息
    
    Args:
        instance_id: 实例ID
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 凭据信息
    """
    try:
        auth_service = InstanceAuthService(db)
        
        credentials = await auth_service.get_instance_credentials(
            tenant_id=tenant.id,
            instance_id=instance_id
        )
        
        if not credentials:
            raise HTTPException(
                status_code=404,
                detail=f"No credentials found for instance: {instance_id}"
            )
        
        return StandardResponse(
            data=credentials,
            message="Instance credentials retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_instance_credentials_error",
                    tenant_id=tenant.id,
                    instance_id=instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get instance credentials"
        )


@router.get("/config/{instance_id}")
async def get_instance_config(
    instance_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    获取实例配置
    
    Args:
        instance_id: 实例ID
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 实例配置
    """
    try:
        config_service = InstanceConfigService(db)
        
        config = await config_service.get_instance_config(
            tenant_id=tenant.id,
            instance_id=instance_id
        )
        
        return StandardResponse(
            data=config,
            message="Instance configuration retrieved successfully"
        )
        
    except Exception as e:
        logger.error("get_instance_config_error",
                    tenant_id=tenant.id,
                    instance_id=instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get instance configuration"
        )


@router.put("/config")
async def update_tenant_config(
    request: InstanceConfigUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    更新租户配置
    
    Args:
        request: 配置更新请求
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 更新结果
    """
    try:
        config_service = InstanceConfigService(db)
        
        result = await config_service.update_tenant_config(
            tenant_id=tenant.id,
            config_updates=request.config_updates,
            auto_push=request.auto_push
        )
        
        logger.info("tenant_config_updated_via_api",
                   tenant_id=tenant.id,
                   updated_fields=list(request.config_updates.keys()),
                   auto_push=request.auto_push)
        
        return StandardResponse(
            data=result,
            message="Tenant configuration updated successfully"
        )
        
    except ValueError as e:
        logger.error("update_tenant_config_validation_error",
                    tenant_id=tenant.id,
                    error=str(e))
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
    except Exception as e:
        logger.error("update_tenant_config_error",
                    tenant_id=tenant.id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to update tenant configuration"
        )


@router.post("/config/push")
async def push_config_to_instance(
    request: ConfigPushRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    推送配置到指定实例
    
    Args:
        request: 配置推送请求
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 推送结果
    """
    try:
        config_service = InstanceConfigService(db)
        
        result = await config_service.push_config_to_instance(
            tenant_id=tenant.id,
            instance_id=request.instance_id,
            config_data=request.config_data,
            instance_endpoint=request.instance_endpoint
        )
        
        logger.info("config_pushed_to_instance_via_api",
                   tenant_id=tenant.id,
                   instance_id=request.instance_id)
        
        return StandardResponse(
            data=result,
            message="Configuration pushed to instance successfully"
        )
        
    except ValueError as e:
        logger.error("push_config_validation_error",
                    tenant_id=tenant.id,
                    instance_id=request.instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
    except ConnectionError as e:
        logger.error("push_config_connection_error",
                    tenant_id=tenant.id,
                    instance_id=request.instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to instance: {str(e)}"
        )
    
    except Exception as e:
        logger.error("push_config_error",
                    tenant_id=tenant.id,
                    instance_id=request.instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to push configuration to instance"
        )


@router.post("/config/broadcast")
async def broadcast_config_update(
    request: ConfigBroadcastRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    广播配置更新到所有实例
    
    Args:
        request: 配置广播请求
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 广播结果
    """
    try:
        config_service = InstanceConfigService(db)
        
        result = await config_service.broadcast_config_update(
            tenant_id=tenant.id,
            config_data=request.config_data,
            instance_filter=request.instance_filter
        )
        
        logger.info("config_broadcast_via_api",
                   tenant_id=tenant.id,
                   total_instances=result.get('total_instances', 0),
                   successful_pushes=result.get('successful_pushes', 0))
        
        return StandardResponse(
            data=result,
            message="Configuration broadcast completed"
        )
        
    except Exception as e:
        logger.error("broadcast_config_error",
                    tenant_id=tenant.id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to broadcast configuration update"
        )


@router.get("/health")
async def instances_health_check(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    实例管理功能健康检查
    
    Args:
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 健康状态
    """
    try:
        # 获取实例Token统计
        auth_service = InstanceAuthService(db)
        tokens = await auth_service.list_instance_tokens(
            tenant_id=tenant.id,
            include_revoked=True
        )
        
        active_tokens = [t for t in tokens if t.get('status') == 'active']
        revoked_tokens = [t for t in tokens if t.get('status') == 'revoked']
        
        # 构建健康状态
        health_status = {
            "status": "healthy",
            "tenant_id": str(tenant.id),
            "services": {
                "instance_auth": "available",
                "config_management": "available",
                "webhook_processing": "available"
            },
            "statistics": {
                "total_tokens": len(tokens),
                "active_tokens": len(active_tokens),
                "revoked_tokens": len(revoked_tokens)
            },
            "endpoints": {
                "token_management": "/api/v1/instances/tokens",
                "config_management": "/api/v1/instances/config",
                "webhook_endpoints": f"/api/v1/webhooks/{tenant.id}"
            }
        }
        
        return StandardResponse(
            data=health_status,
            message="Instance management is healthy"
        )
        
    except Exception as e:
        logger.error("instances_health_check_error",
                    tenant_id=tenant.id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Health check failed"
        ) 