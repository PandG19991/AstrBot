"""
Webhook接收服务

处理AstrBot实例的消息上报、状态同步和事件通知
"""
import logging
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.services.message_service import MessageService
from app.services.session_service import SessionService
from app.schemas.message import MessageCreate, MessageType
from app.models.tenant import Tenant

# 配置日志
logger = logging.getLogger(__name__)


class WebhookService:
    """Webhook接收服务"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化Webhook服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.message_service = MessageService(db)
        self.session_service = SessionService(db)
    
    async def process_message_webhook(
        self,
        tenant_id: UUID,
        webhook_data: Dict[str, Any],
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理消息上报Webhook
        
        Args:
            tenant_id: 租户ID
            webhook_data: Webhook数据
            signature: 签名（用于验证）
            
        Returns:
            Dict[str, Any]: 处理结果
            
        Raises:
            ValueError: 数据格式错误
            SecurityError: 签名验证失败
        """
        try:
            # 验证签名
            if signature:
                await self._verify_webhook_signature(tenant_id, webhook_data, signature)
            
            # 解析Webhook数据
            event_type = webhook_data.get('event_type')
            event_data = webhook_data.get('data', {})
            
            # 根据事件类型处理
            if event_type == 'message.received':
                result = await self._handle_message_received(tenant_id, event_data)
            elif event_type == 'message.sent':
                result = await self._handle_message_sent(tenant_id, event_data)
            elif event_type == 'session.created':
                result = await self._handle_session_created(tenant_id, event_data)
            elif event_type == 'session.closed':
                result = await self._handle_session_closed(tenant_id, event_data)
            else:
                result = await self._handle_unknown_event(tenant_id, event_type, event_data)
            
            logger.info("webhook_processed_successfully",
                       tenant_id=tenant_id,
                       event_type=event_type,
                       result=result)
            
            return {
                "status": "success",
                "event_type": event_type,
                "result": result,
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("webhook_processing_error",
                        tenant_id=tenant_id,
                        error=str(e),
                        webhook_data=webhook_data)
            raise
    
    async def process_status_webhook(
        self,
        tenant_id: UUID,
        webhook_data: Dict[str, Any],
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理状态同步Webhook
        
        Args:
            tenant_id: 租户ID
            webhook_data: Webhook数据
            signature: 签名
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 验证签名
            if signature:
                await self._verify_webhook_signature(tenant_id, webhook_data, signature)
            
            # 解析状态数据
            instance_id = webhook_data.get('instance_id')
            status = webhook_data.get('status')
            metadata = webhook_data.get('metadata', {})
            
            # 更新实例状态
            result = await self._update_instance_status(
                tenant_id=tenant_id,
                instance_id=instance_id,
                status=status,
                metadata=metadata
            )
            
            logger.info("status_webhook_processed",
                       tenant_id=tenant_id,
                       instance_id=instance_id,
                       status=status)
            
            return {
                "status": "success",
                "instance_id": instance_id,
                "updated_status": status,
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("status_webhook_processing_error",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def _handle_message_received(
        self,
        tenant_id: UUID,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理接收到的消息事件
        
        Args:
            tenant_id: 租户ID
            event_data: 事件数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 提取消息信息
        session_id = event_data.get('session_id')
        user_id = event_data.get('user_id')
        content = event_data.get('content')
        platform = event_data.get('platform')
        message_metadata = event_data.get('metadata', {})
        
        # 验证必需字段
        if not all([session_id, user_id, content]):
            raise ValueError("Missing required fields: session_id, user_id, content")
        
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            raise ValueError(f"Invalid session_id format: {session_id}")
        
        # 确保会话存在
        session = await self.session_service.get_session(session_uuid, tenant_id)
        if not session:
            # 创建新会话
            from app.schemas.session import SessionCreate
            session_create = SessionCreate(
                user_id=user_id,
                platform=platform or "unknown",
                metadata={"created_via": "webhook"}
            )
            session = await self.session_service.create_or_get_session(session_create, tenant_id)
        
        # 创建消息
        message_create = MessageCreate(
            session_id=session_uuid,
            content=content,
            message_type=MessageType.user,
            user_id=user_id,
            metadata={
                **message_metadata,
                "platform": platform,
                "source": "webhook",
                "received_at": datetime.utcnow().isoformat()
            }
        )
        
        # 保存消息
        message = await self.message_service.store_message(message_create, tenant_id)
        
        return {
            "action": "message_stored",
            "message_id": str(message.id),
            "session_id": str(session.id),
            "user_id": user_id
        }
    
    async def _handle_message_sent(
        self,
        tenant_id: UUID,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理发送消息事件
        
        Args:
            tenant_id: 租户ID
            event_data: 事件数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 提取消息信息
        session_id = event_data.get('session_id')
        content = event_data.get('content')
        agent_id = event_data.get('agent_id', 'system')
        message_metadata = event_data.get('metadata', {})
        
        if not all([session_id, content]):
            raise ValueError("Missing required fields: session_id, content")
        
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            raise ValueError(f"Invalid session_id format: {session_id}")
        
        # 创建代理消息
        message_create = MessageCreate(
            session_id=session_uuid,
            content=content,
            message_type=MessageType.agent,
            user_id=agent_id,
            metadata={
                **message_metadata,
                "source": "webhook",
                "sent_at": datetime.utcnow().isoformat()
            }
        )
        
        # 保存消息
        message = await self.message_service.store_message(message_create, tenant_id)
        
        return {
            "action": "agent_message_stored",
            "message_id": str(message.id),
            "session_id": session_id,
            "agent_id": agent_id
        }
    
    async def _handle_session_created(
        self,
        tenant_id: UUID,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理会话创建事件
        
        Args:
            tenant_id: 租户ID
            event_data: 事件数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        user_id = event_data.get('user_id')
        platform = event_data.get('platform')
        session_metadata = event_data.get('metadata', {})
        
        if not user_id:
            raise ValueError("Missing required field: user_id")
        
        # 创建会话
        from app.schemas.session import SessionCreate
        session_create = SessionCreate(
            user_id=user_id,
            platform=platform or "unknown",
            metadata={
                **session_metadata,
                "created_via": "webhook"
            }
        )
        
        session = await self.session_service.create_or_get_session(session_create, tenant_id)
        
        return {
            "action": "session_created",
            "session_id": str(session.id),
            "user_id": user_id,
            "platform": platform
        }
    
    async def _handle_session_closed(
        self,
        tenant_id: UUID,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理会话关闭事件
        
        Args:
            tenant_id: 租户ID
            event_data: 事件数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        session_id = event_data.get('session_id')
        close_reason = event_data.get('reason', 'completed')
        
        if not session_id:
            raise ValueError("Missing required field: session_id")
        
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            raise ValueError(f"Invalid session_id format: {session_id}")
        
        # 更新会话状态
        updated_session = await self.session_service.update_session_status(
            session_id=session_uuid,
            tenant_id=tenant_id,
            status="closed",
            metadata={"close_reason": close_reason, "closed_via": "webhook"}
        )
        
        return {
            "action": "session_closed",
            "session_id": session_id,
            "reason": close_reason,
            "closed_at": datetime.utcnow().isoformat()
        }
    
    async def _handle_unknown_event(
        self,
        tenant_id: UUID,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        处理未知事件类型
        
        Args:
            tenant_id: 租户ID
            event_type: 事件类型
            event_data: 事件数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        logger.warning("unknown_webhook_event_type",
                      tenant_id=tenant_id,
                      event_type=event_type,
                      event_data=event_data)
        
        return {
            "action": "ignored",
            "reason": f"Unknown event type: {event_type}",
            "event_type": event_type
        }
    
    async def _update_instance_status(
        self,
        tenant_id: UUID,
        instance_id: str,
        status: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        更新AstrBot实例状态
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            status: 状态
            metadata: 元数据
            
        Returns:
            Dict[str, Any]: 更新结果
        """
        # 这里应该更新实例状态表
        # 由于当前没有实例模型，暂时记录日志
        logger.info("instance_status_updated",
                   tenant_id=tenant_id,
                   instance_id=instance_id,
                   status=status,
                   metadata=metadata)
        
        # TODO: 实现实例状态数据库更新
        return {
            "instance_id": instance_id,
            "previous_status": "unknown",
            "new_status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    async def _verify_webhook_signature(
        self,
        tenant_id: UUID,
        webhook_data: Dict[str, Any],
        signature: str
    ) -> bool:
        """
        验证Webhook签名
        
        Args:
            tenant_id: 租户ID
            webhook_data: Webhook数据
            signature: 签名
            
        Returns:
            bool: 验证结果
            
        Raises:
            SecurityError: 签名验证失败
        """
        try:
            # 获取租户的Webhook密钥
            webhook_secret = await self._get_tenant_webhook_secret(tenant_id)
            
            if not webhook_secret:
                logger.warning("no_webhook_secret_configured",
                              tenant_id=tenant_id)
                return True  # 如果没有配置密钥，跳过验证
            
            # 计算期望的签名
            payload = json.dumps(webhook_data, sort_keys=True, separators=(',', ':'))
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # 验证签名
            provided_signature = signature.replace('sha256=', '') if signature.startswith('sha256=') else signature
            
            if not hmac.compare_digest(expected_signature, provided_signature):
                logger.error("webhook_signature_verification_failed",
                            tenant_id=tenant_id,
                            expected=expected_signature[:8] + "...",
                            provided=provided_signature[:8] + "...")
                raise SecurityError("Webhook signature verification failed")
            
            return True
            
        except Exception as e:
            logger.error("webhook_signature_verification_error",
                        tenant_id=tenant_id,
                        error=str(e))
            raise SecurityError(f"Signature verification error: {str(e)}")
    
    async def _get_tenant_webhook_secret(self, tenant_id: UUID) -> Optional[str]:
        """
        获取租户的Webhook密钥
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            Optional[str]: Webhook密钥
        """
        try:
            # 查询租户配置
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if tenant and tenant.configuration:
                return tenant.configuration.get('webhook_secret')
            
            return None
            
        except Exception as e:
            logger.error("get_webhook_secret_error",
                        tenant_id=tenant_id,
                        error=str(e))
            return None
    
    async def validate_webhook_data(self, webhook_data: Dict[str, Any]) -> bool:
        """
        验证Webhook数据格式
        
        Args:
            webhook_data: Webhook数据
            
        Returns:
            bool: 验证结果
            
        Raises:
            ValueError: 数据格式错误
        """
        # 验证基本结构
        if not isinstance(webhook_data, dict):
            raise ValueError("Webhook data must be a JSON object")
        
        # 验证必需字段
        required_fields = ['event_type', 'timestamp']
        for field in required_fields:
            if field not in webhook_data:
                raise ValueError(f"Missing required field: {field}")
        
        # 验证事件类型
        valid_event_types = [
            'message.received',
            'message.sent',
            'session.created',
            'session.closed',
            'instance.status_changed'
        ]
        
        event_type = webhook_data.get('event_type')
        if event_type not in valid_event_types:
            logger.warning("unknown_event_type",
                          event_type=event_type,
                          valid_types=valid_event_types)
        
        # 验证时间戳
        timestamp = webhook_data.get('timestamp')
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid timestamp format: {timestamp}")
        
        return True


class SecurityError(Exception):
    """安全相关错误"""
    pass 