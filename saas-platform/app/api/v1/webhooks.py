"""
Webhook API端点

处理AstrBot实例的消息上报、状态同步等Webhook请求
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Header, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_tenant_from_token
from app.services.webhook_service import WebhookService
from app.services.instance_auth_service import InstanceAuthService
from app.schemas.common import StandardResponse
from app.models.tenant import Tenant

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{tenant_id}/messages")
async def receive_message_webhook(
    tenant_id: UUID,
    webhook_data: Dict[str, Any],
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_instance_id: Optional[str] = Header(None, alias="X-Instance-ID"),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    接收AstrBot实例的消息Webhook
    
    Args:
        tenant_id: 租户ID
        webhook_data: Webhook数据
        x_signature: Webhook签名
        x_instance_id: 实例ID
        db: 数据库会话
        
    Returns:
        StandardResponse: 处理结果
        
    Raises:
        HTTPException: 处理失败
    """
    try:
        # 验证实例认证
        if x_instance_id and x_signature:
            auth_service = InstanceAuthService(db)
            is_valid = await auth_service.verify_webhook_signature(
                tenant_id=tenant_id,
                instance_id=x_instance_id,
                webhook_data=webhook_data,
                signature=x_signature
            )
            
            if not is_valid:
                logger.warning("webhook_signature_verification_failed",
                              tenant_id=tenant_id,
                              instance_id=x_instance_id,
                              remote_addr=request.client.host if request.client else "unknown")
                raise HTTPException(
                    status_code=401,
                    detail="Webhook signature verification failed"
                )
        
        # 处理Webhook
        webhook_service = WebhookService(db)
        
        # 验证Webhook数据格式
        await webhook_service.validate_webhook_data(webhook_data)
        
        # 处理消息Webhook
        result = await webhook_service.process_message_webhook(
            tenant_id=tenant_id,
            webhook_data=webhook_data,
            signature=x_signature
        )
        
        logger.info("message_webhook_processed_successfully",
                   tenant_id=tenant_id,
                   instance_id=x_instance_id,
                   event_type=webhook_data.get('event_type'))
        
        return StandardResponse(
            data=result,
            message="Message webhook processed successfully"
        )
        
    except ValueError as e:
        logger.error("webhook_validation_error",
                    tenant_id=tenant_id,
                    instance_id=x_instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid webhook data: {str(e)}"
        )
    
    except Exception as e:
        logger.error("message_webhook_processing_error",
                    tenant_id=tenant_id,
                    instance_id=x_instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to process message webhook"
        )


@router.post("/{tenant_id}/status")
async def receive_status_webhook(
    tenant_id: UUID,
    webhook_data: Dict[str, Any],
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_instance_id: Optional[str] = Header(None, alias="X-Instance-ID"),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    接收AstrBot实例的状态同步Webhook
    
    Args:
        tenant_id: 租户ID
        webhook_data: Webhook数据
        x_signature: Webhook签名
        x_instance_id: 实例ID
        db: 数据库会话
        
    Returns:
        StandardResponse: 处理结果
    """
    try:
        # 验证实例认证
        if x_instance_id and x_signature:
            auth_service = InstanceAuthService(db)
            is_valid = await auth_service.verify_webhook_signature(
                tenant_id=tenant_id,
                instance_id=x_instance_id,
                webhook_data=webhook_data,
                signature=x_signature
            )
            
            if not is_valid:
                logger.warning("status_webhook_signature_verification_failed",
                              tenant_id=tenant_id,
                              instance_id=x_instance_id)
                raise HTTPException(
                    status_code=401,
                    detail="Webhook signature verification failed"
                )
        
        # 处理状态Webhook
        webhook_service = WebhookService(db)
        result = await webhook_service.process_status_webhook(
            tenant_id=tenant_id,
            webhook_data=webhook_data,
            signature=x_signature
        )
        
        logger.info("status_webhook_processed_successfully",
                   tenant_id=tenant_id,
                   instance_id=x_instance_id)
        
        return StandardResponse(
            data=result,
            message="Status webhook processed successfully"
        )
        
    except Exception as e:
        logger.error("status_webhook_processing_error",
                    tenant_id=tenant_id,
                    instance_id=x_instance_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to process status webhook"
        )


@router.get("/{tenant_id}/health")
async def webhook_health_check(
    tenant_id: UUID,
    tenant: Tenant = Depends(get_current_tenant_from_token),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    Webhook健康检查端点
    
    Args:
        tenant_id: 租户ID
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 健康状态
    """
    try:
        # 验证租户权限
        if tenant.id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: tenant ID mismatch"
            )
        
        # 检查Webhook配置
        webhook_config = {}
        if tenant.configuration:
            webhook_config = tenant.configuration.get('webhook_config', {})
        
        # 构建健康状态
        health_status = {
            "status": "healthy",
            "tenant_id": str(tenant_id),
            "webhook_endpoints": {
                "messages": f"/api/v1/webhooks/{tenant_id}/messages",
                "status": f"/api/v1/webhooks/{tenant_id}/status"
            },
            "webhook_config": {
                "has_secret": bool(webhook_config.get('webhook_secret')),
                "max_payload_size": webhook_config.get('max_payload_size', 1048576),  # 1MB
                "timeout_seconds": webhook_config.get('timeout_seconds', 30)
            },
            "checked_at": webhook_data.get('timestamp', 'unknown') if 'webhook_data' in locals() else None
        }
        
        return StandardResponse(
            data=health_status,
            message="Webhook endpoint is healthy"
        )
        
    except Exception as e:
        logger.error("webhook_health_check_error",
                    tenant_id=tenant_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Health check failed"
        )


@router.post("/{tenant_id}/test")
async def test_webhook_endpoint(
    tenant_id: UUID,
    test_data: Optional[Dict[str, Any]] = None,
    tenant: Tenant = Depends(get_current_tenant_from_token),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    测试Webhook端点
    
    Args:
        tenant_id: 租户ID
        test_data: 测试数据
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: 测试结果
    """
    try:
        # 验证租户权限
        if tenant.id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: tenant ID mismatch"
            )
        
        # 构建默认测试数据
        if not test_data:
            test_data = {
                "event_type": "test.webhook",
                "timestamp": "2024-01-01T12:00:00Z",
                "data": {
                    "test": True,
                    "message": "This is a test webhook"
                }
            }
        
        # 验证测试数据格式
        webhook_service = WebhookService(db)
        try:
            await webhook_service.validate_webhook_data(test_data)
        except ValueError as ve:
            # 对于测试端点，我们可以更宽松一些
            logger.warning("test_webhook_validation_warning",
                          tenant_id=tenant_id,
                          validation_error=str(ve))
        
        # 模拟处理测试Webhook
        test_result = {
            "status": "test_successful",
            "tenant_id": str(tenant_id),
            "test_data": test_data,
            "endpoints_available": [
                f"/api/v1/webhooks/{tenant_id}/messages",
                f"/api/v1/webhooks/{tenant_id}/status"
            ],
            "tested_at": webhook_data.get('timestamp', 'unknown') if 'webhook_data' in locals() else None
        }
        
        logger.info("webhook_test_completed",
                   tenant_id=tenant_id,
                   test_data=test_data)
        
        return StandardResponse(
            data=test_result,
            message="Webhook test completed successfully"
        )
        
    except Exception as e:
        logger.error("webhook_test_error",
                    tenant_id=tenant_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Webhook test failed"
        )


@router.get("/{tenant_id}/config")
async def get_webhook_config(
    tenant_id: UUID,
    tenant: Tenant = Depends(get_current_tenant_from_token),
    db: AsyncSession = Depends(get_db)
) -> StandardResponse:
    """
    获取Webhook配置
    
    Args:
        tenant_id: 租户ID
        tenant: 当前租户
        db: 数据库会话
        
    Returns:
        StandardResponse: Webhook配置
    """
    try:
        # 验证租户权限
        if tenant.id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: tenant ID mismatch"
            )
        
        # 获取Webhook配置
        webhook_config = {}
        if tenant.configuration:
            webhook_config = tenant.configuration.get('webhook_config', {})
        
        # 构建配置响应（不包含敏感信息）
        config_response = {
            "tenant_id": str(tenant_id),
            "webhook_endpoints": {
                "messages": f"/api/v1/webhooks/{tenant_id}/messages",
                "status": f"/api/v1/webhooks/{tenant_id}/status",
                "test": f"/api/v1/webhooks/{tenant_id}/test"
            },
            "config": {
                "has_webhook_secret": bool(webhook_config.get('webhook_secret')),
                "max_payload_size": webhook_config.get('max_payload_size', 1048576),
                "timeout_seconds": webhook_config.get('timeout_seconds', 30),
                "retry_attempts": webhook_config.get('retry_attempts', 3),
                "signature_verification": webhook_config.get('signature_verification', True)
            },
            "supported_events": [
                "message.received",
                "message.sent", 
                "session.created",
                "session.closed",
                "instance.status_changed"
            ]
        }
        
        return StandardResponse(
            data=config_response,
            message="Webhook configuration retrieved successfully"
        )
        
    except Exception as e:
        logger.error("get_webhook_config_error",
                    tenant_id=tenant_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to get webhook configuration"
        ) 