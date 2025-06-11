"""
实例认证服务

管理AstrBot实例的API Key管理和Webhook签名验证机制
"""
import logging
import secrets
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.tenant import Tenant

# 配置日志
logger = logging.getLogger(__name__)


class InstanceAuthService:
    """实例认证服务"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化实例认证服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def generate_instance_token(
        self,
        tenant_id: UUID,
        instance_id: str,
        instance_name: Optional[str] = None,
        expires_days: int = 365
    ) -> Dict[str, Any]:
        """
        为AstrBot实例生成认证Token
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            instance_name: 实例名称
            expires_days: 过期天数
            
        Returns:
            Dict[str, Any]: Token信息
            
        Raises:
            ValueError: 参数错误
        """
        try:
            # 验证输入参数
            if not instance_id:
                raise ValueError("Instance ID is required")
            
            # 生成Token
            token = self._generate_secure_token()
            secret = self._generate_webhook_secret()
            
            # 计算过期时间
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
            
            # 构建Token信息
            token_info = {
                "instance_id": instance_id,
                "instance_name": instance_name or instance_id,
                "token": token,
                "webhook_secret": secret,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat(),
                "status": "active"
            }
            
            # 保存到租户配置
            await self._save_instance_token(tenant_id, instance_id, token_info)
            
            logger.info("instance_token_generated",
                       tenant_id=tenant_id,
                       instance_id=instance_id,
                       expires_at=expires_at.isoformat())
            
            return {
                "status": "success",
                "instance_id": instance_id,
                "api_token": token,
                "webhook_secret": secret,
                "expires_at": expires_at.isoformat(),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("generate_instance_token_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            raise
    
    async def validate_instance_token(
        self,
        tenant_id: UUID,
        instance_id: str,
        token: str
    ) -> bool:
        """
        验证实例Token
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            token: 待验证的Token
            
        Returns:
            bool: 验证结果
        """
        try:
            # 获取实例Token信息
            token_info = await self._get_instance_token_info(tenant_id, instance_id)
            
            if not token_info:
                logger.warning("instance_token_not_found",
                              tenant_id=tenant_id,
                              instance_id=instance_id)
                return False
            
            # 检查Token状态
            if token_info.get('status') != 'active':
                logger.warning("instance_token_inactive",
                              tenant_id=tenant_id,
                              instance_id=instance_id,
                              status=token_info.get('status'))
                return False
            
            # 检查过期时间
            expires_at_str = token_info.get('expires_at')
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.utcnow() > expires_at:
                    logger.warning("instance_token_expired",
                                  tenant_id=tenant_id,
                                  instance_id=instance_id,
                                  expires_at=expires_at_str)
                    return False
            
            # 验证Token
            stored_token = token_info.get('token')
            if not stored_token or not hmac.compare_digest(stored_token, token):
                logger.warning("instance_token_mismatch",
                              tenant_id=tenant_id,
                              instance_id=instance_id)
                return False
            
            logger.info("instance_token_validated",
                       tenant_id=tenant_id,
                       instance_id=instance_id)
            
            return True
            
        except Exception as e:
            logger.error("validate_instance_token_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            return False
    
    async def revoke_instance_token(
        self,
        tenant_id: UUID,
        instance_id: str
    ) -> Dict[str, Any]:
        """
        撤销实例Token
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            
        Returns:
            Dict[str, Any]: 撤销结果
        """
        try:
            # 获取当前Token信息
            token_info = await self._get_instance_token_info(tenant_id, instance_id)
            
            if not token_info:
                raise ValueError(f"No token found for instance: {instance_id}")
            
            # 更新Token状态为已撤销
            token_info['status'] = 'revoked'
            token_info['revoked_at'] = datetime.utcnow().isoformat()
            
            # 保存更新
            await self._save_instance_token(tenant_id, instance_id, token_info)
            
            logger.info("instance_token_revoked",
                       tenant_id=tenant_id,
                       instance_id=instance_id)
            
            return {
                "status": "success",
                "instance_id": instance_id,
                "revoked_at": datetime.utcnow().isoformat(),
                "message": "Token revoked successfully"
            }
            
        except Exception as e:
            logger.error("revoke_instance_token_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            raise
    
    async def rotate_instance_token(
        self,
        tenant_id: UUID,
        instance_id: str,
        expires_days: int = 365
    ) -> Dict[str, Any]:
        """
        轮换实例Token（生成新Token并撤销旧Token）
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            expires_days: 新Token过期天数
            
        Returns:
            Dict[str, Any]: 新Token信息
        """
        try:
            # 撤销旧Token
            await self.revoke_instance_token(tenant_id, instance_id)
            
            # 生成新Token
            new_token_result = await self.generate_instance_token(
                tenant_id=tenant_id,
                instance_id=instance_id,
                expires_days=expires_days
            )
            
            logger.info("instance_token_rotated",
                       tenant_id=tenant_id,
                       instance_id=instance_id)
            
            return {
                **new_token_result,
                "action": "rotated",
                "message": "Token rotated successfully"
            }
            
        except Exception as e:
            logger.error("rotate_instance_token_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            raise
    
    async def list_instance_tokens(
        self,
        tenant_id: UUID,
        include_revoked: bool = False
    ) -> List[Dict[str, Any]]:
        """
        列出租户的所有实例Token
        
        Args:
            tenant_id: 租户ID
            include_revoked: 是否包含已撤销的Token
            
        Returns:
            List[Dict[str, Any]]: Token列表
        """
        try:
            # 获取租户配置
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if not tenant or not tenant.configuration:
                return []
            
            # 获取实例Token
            instance_tokens = tenant.configuration.get('instance_tokens', {})
            
            token_list = []
            for instance_id, token_info in instance_tokens.items():
                # 过滤已撤销的Token
                if not include_revoked and token_info.get('status') == 'revoked':
                    continue
                
                # 移除敏感信息
                safe_token_info = {
                    "instance_id": instance_id,
                    "instance_name": token_info.get('instance_name'),
                    "created_at": token_info.get('created_at'),
                    "expires_at": token_info.get('expires_at'),
                    "status": token_info.get('status'),
                    "revoked_at": token_info.get('revoked_at')
                }
                
                token_list.append(safe_token_info)
            
            return token_list
            
        except Exception as e:
            logger.error("list_instance_tokens_error",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def verify_webhook_signature(
        self,
        tenant_id: UUID,
        instance_id: str,
        webhook_data: Dict[str, Any],
        signature: str
    ) -> bool:
        """
        验证Webhook签名
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            webhook_data: Webhook数据
            signature: 提供的签名
            
        Returns:
            bool: 验证结果
        """
        try:
            # 获取实例的Webhook密钥
            token_info = await self._get_instance_token_info(tenant_id, instance_id)
            
            if not token_info:
                logger.warning("webhook_signature_no_token_info",
                              tenant_id=tenant_id,
                              instance_id=instance_id)
                return False
            
            webhook_secret = token_info.get('webhook_secret')
            if not webhook_secret:
                logger.warning("webhook_signature_no_secret",
                              tenant_id=tenant_id,
                              instance_id=instance_id)
                return False
            
            # 计算期望的签名
            payload = json.dumps(webhook_data, sort_keys=True, separators=(',', ':'))
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # 验证签名
            provided_signature = signature.replace('sha256=', '') if signature.startswith('sha256=') else signature
            
            is_valid = hmac.compare_digest(expected_signature, provided_signature)
            
            if is_valid:
                logger.info("webhook_signature_verified",
                           tenant_id=tenant_id,
                           instance_id=instance_id)
            else:
                logger.warning("webhook_signature_verification_failed",
                              tenant_id=tenant_id,
                              instance_id=instance_id,
                              expected=expected_signature[:8] + "...",
                              provided=provided_signature[:8] + "...")
            
            return is_valid
            
        except Exception as e:
            logger.error("verify_webhook_signature_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            return False
    
    async def get_instance_credentials(
        self,
        tenant_id: UUID,
        instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取实例认证凭据（不包含敏感信息）
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            
        Returns:
            Optional[Dict[str, Any]]: 实例凭据信息
        """
        try:
            token_info = await self._get_instance_token_info(tenant_id, instance_id)
            
            if not token_info:
                return None
            
            # 返回安全的凭据信息
            return {
                "instance_id": instance_id,
                "instance_name": token_info.get('instance_name'),
                "status": token_info.get('status'),
                "created_at": token_info.get('created_at'),
                "expires_at": token_info.get('expires_at'),
                "has_webhook_secret": bool(token_info.get('webhook_secret'))
            }
            
        except Exception as e:
            logger.error("get_instance_credentials_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            return None
    
    async def cleanup_expired_tokens(self, tenant_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        清理过期的Token
        
        Args:
            tenant_id: 租户ID（可选，不提供则清理所有租户）
            
        Returns:
            Dict[str, Any]: 清理结果
        """
        try:
            cleaned_count = 0
            total_checked = 0
            
            # 构建查询条件
            if tenant_id:
                stmt = select(Tenant).where(Tenant.id == tenant_id)
            else:
                stmt = select(Tenant)
            
            result = await self.db.execute(stmt)
            tenants = result.scalars().all()
            
            current_time = datetime.utcnow()
            
            for tenant in tenants:
                if not tenant.configuration:
                    continue
                
                instance_tokens = tenant.configuration.get('instance_tokens', {})
                updated_tokens = {}
                
                for inst_id, token_info in instance_tokens.items():
                    total_checked += 1
                    
                    # 检查是否过期
                    expires_at_str = token_info.get('expires_at')
                    if expires_at_str:
                        try:
                            expires_at = datetime.fromisoformat(expires_at_str)
                            if current_time > expires_at and token_info.get('status') == 'active':
                                # 标记为过期
                                token_info['status'] = 'expired'
                                token_info['expired_at'] = current_time.isoformat()
                                cleaned_count += 1
                                
                                logger.info("token_marked_expired",
                                           tenant_id=tenant.id,
                                           instance_id=inst_id,
                                           expires_at=expires_at_str)
                        except ValueError:
                            logger.warning("invalid_expires_at_format",
                                          tenant_id=tenant.id,
                                          instance_id=inst_id,
                                          expires_at=expires_at_str)
                    
                    updated_tokens[inst_id] = token_info
                
                # 更新租户配置
                if updated_tokens != instance_tokens:
                    tenant.configuration['instance_tokens'] = updated_tokens
                    await self.db.commit()
            
            logger.info("expired_tokens_cleanup_completed",
                       tenant_id=tenant_id,
                       cleaned_count=cleaned_count,
                       total_checked=total_checked)
            
            return {
                "status": "completed",
                "cleaned_count": cleaned_count,
                "total_checked": total_checked,
                "cleaned_at": current_time.isoformat()
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error("cleanup_expired_tokens_error",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    def _generate_secure_token(self) -> str:
        """
        生成安全的认证Token
        
        Returns:
            str: 安全Token
        """
        # 生成32字节的随机Token
        token = secrets.token_urlsafe(32)
        return f"astrbot_{token}"
    
    def _generate_webhook_secret(self) -> str:
        """
        生成Webhook密钥
        
        Returns:
            str: Webhook密钥
        """
        # 生成16字节的随机密钥
        return secrets.token_hex(16)
    
    async def _save_instance_token(
        self,
        tenant_id: UUID,
        instance_id: str,
        token_info: Dict[str, Any]
    ) -> None:
        """
        保存实例Token信息到数据库
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            token_info: Token信息
        """
        try:
            # 获取租户
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # 更新配置
            if not tenant.configuration:
                tenant.configuration = {}
            
            if 'instance_tokens' not in tenant.configuration:
                tenant.configuration['instance_tokens'] = {}
            
            tenant.configuration['instance_tokens'][instance_id] = token_info
            
            # 保存到数据库
            await self.db.commit()
            
        except Exception as e:
            await self.db.rollback()
            logger.error("save_instance_token_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            raise
    
    async def _get_instance_token_info(
        self,
        tenant_id: UUID,
        instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取实例Token信息
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            
        Returns:
            Optional[Dict[str, Any]]: Token信息
        """
        try:
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if not tenant or not tenant.configuration:
                return None
            
            instance_tokens = tenant.configuration.get('instance_tokens', {})
            return instance_tokens.get(instance_id)
            
        except Exception as e:
            logger.error("get_instance_token_info_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            return None 