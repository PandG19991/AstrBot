"""
实例配置管理服务

管理租户配置向AstrBot实例的推送和配置热更新机制
"""
import logging
import json
import httpx
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Tenant

# 配置日志
logger = logging.getLogger(__name__)


class InstanceConfigService:
    """实例配置管理服务"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化实例配置服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self._http_client = httpx.AsyncClient(timeout=30.0)
    
    async def push_config_to_instance(
        self,
        tenant_id: UUID,
        instance_id: str,
        config_data: Dict[str, Any],
        instance_endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        推送配置到AstrBot实例
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            config_data: 配置数据
            instance_endpoint: 实例端点URL
            
        Returns:
            Dict[str, Any]: 推送结果
            
        Raises:
            ValueError: 参数错误
            ConnectionError: 连接实例失败
        """
        try:
            # 验证输入参数
            if not instance_id:
                raise ValueError("Instance ID is required")
            
            # 获取实例端点
            if not instance_endpoint:
                instance_endpoint = await self._get_instance_endpoint(tenant_id, instance_id)
            
            if not instance_endpoint:
                raise ValueError(f"No endpoint configured for instance: {instance_id}")
            
            # 构建配置推送请求
            push_url = f"{instance_endpoint}/api/config/update"
            
            # 获取认证信息
            auth_token = await self._get_instance_auth_token(tenant_id, instance_id)
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "AstrBot-SaaS/1.0"
            }
            
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            
            # 构建请求体
            request_body = {
                "tenant_id": str(tenant_id),
                "instance_id": instance_id,
                "config": config_data,
                "timestamp": datetime.utcnow().isoformat(),
                "version": await self._get_config_version(tenant_id)
            }
            
            # 发送配置推送请求
            response = await self._http_client.post(
                push_url,
                json=request_body,
                headers=headers
            )
            
            # 处理响应
            if response.status_code == 200:
                result = response.json()
                logger.info("config_pushed_successfully",
                           tenant_id=tenant_id,
                           instance_id=instance_id,
                           endpoint=instance_endpoint)
                
                return {
                    "status": "success",
                    "instance_id": instance_id,
                    "endpoint": instance_endpoint,
                    "response": result,
                    "pushed_at": datetime.utcnow().isoformat()
                }
            else:
                error_detail = f"HTTP {response.status_code}: {response.text}"
                logger.error("config_push_failed",
                            tenant_id=tenant_id,
                            instance_id=instance_id,
                            error=error_detail)
                
                raise ConnectionError(f"Failed to push config: {error_detail}")
                
        except httpx.RequestError as e:
            logger.error("config_push_request_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            raise ConnectionError(f"Request error: {str(e)}")
        
        except Exception as e:
            logger.error("config_push_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            raise
    
    async def broadcast_config_update(
        self,
        tenant_id: UUID,
        config_data: Dict[str, Any],
        instance_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        广播配置更新到所有实例
        
        Args:
            tenant_id: 租户ID
            config_data: 配置数据
            instance_filter: 实例过滤条件
            
        Returns:
            Dict[str, Any]: 广播结果
        """
        try:
            # 获取租户的所有实例
            instances = await self._get_tenant_instances(tenant_id, instance_filter)
            
            if not instances:
                logger.warning("no_instances_found_for_broadcast",
                              tenant_id=tenant_id)
                return {
                    "status": "no_instances",
                    "message": "No instances found for configuration broadcast",
                    "tenant_id": str(tenant_id)
                }
            
            # 并发推送配置到所有实例
            push_results = []
            failed_instances = []
            
            for instance in instances:
                try:
                    result = await self.push_config_to_instance(
                        tenant_id=tenant_id,
                        instance_id=instance['instance_id'],
                        config_data=config_data,
                        instance_endpoint=instance.get('endpoint')
                    )
                    push_results.append({
                        "instance_id": instance['instance_id'],
                        "status": "success",
                        "result": result
                    })
                    
                except Exception as e:
                    failed_instances.append({
                        "instance_id": instance['instance_id'],
                        "error": str(e)
                    })
                    logger.error("instance_config_push_failed",
                                tenant_id=tenant_id,
                                instance_id=instance['instance_id'],
                                error=str(e))
            
            # 构建广播结果
            broadcast_result = {
                "status": "completed",
                "tenant_id": str(tenant_id),
                "total_instances": len(instances),
                "successful_pushes": len(push_results),
                "failed_pushes": len(failed_instances),
                "results": push_results,
                "failures": failed_instances,
                "broadcast_at": datetime.utcnow().isoformat()
            }
            
            logger.info("config_broadcast_completed",
                       tenant_id=tenant_id,
                       total=len(instances),
                       successful=len(push_results),
                       failed=len(failed_instances))
            
            return broadcast_result
            
        except Exception as e:
            logger.error("config_broadcast_error",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def get_instance_config(
        self,
        tenant_id: UUID,
        instance_id: str
    ) -> Dict[str, Any]:
        """
        获取实例配置
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            
        Returns:
            Dict[str, Any]: 实例配置
        """
        try:
            # 获取租户基础配置
            tenant_config = await self._get_tenant_base_config(tenant_id)
            
            # 获取实例特定配置
            instance_config = await self._get_instance_specific_config(tenant_id, instance_id)
            
            # 合并配置
            merged_config = {
                **tenant_config,
                **instance_config,
                "tenant_id": str(tenant_id),
                "instance_id": instance_id,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return merged_config
            
        except Exception as e:
            logger.error("get_instance_config_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            raise
    
    async def update_tenant_config(
        self,
        tenant_id: UUID,
        config_updates: Dict[str, Any],
        auto_push: bool = True
    ) -> Dict[str, Any]:
        """
        更新租户配置
        
        Args:
            tenant_id: 租户ID
            config_updates: 配置更新
            auto_push: 是否自动推送到实例
            
        Returns:
            Dict[str, Any]: 更新结果
        """
        try:
            # 验证配置更新
            validated_updates = await self._validate_config_updates(config_updates)
            
            # 更新租户配置
            await self._update_tenant_configuration(tenant_id, validated_updates)
            
            result = {
                "status": "updated",
                "tenant_id": str(tenant_id),
                "updated_fields": list(validated_updates.keys()),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # 自动推送配置更新
            if auto_push:
                broadcast_result = await self.broadcast_config_update(
                    tenant_id=tenant_id,
                    config_data=await self._get_tenant_base_config(tenant_id)
                )
                result["broadcast_result"] = broadcast_result
            
            logger.info("tenant_config_updated",
                       tenant_id=tenant_id,
                       updated_fields=list(validated_updates.keys()),
                       auto_push=auto_push)
            
            return result
            
        except Exception as e:
            logger.error("update_tenant_config_error",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def _get_instance_endpoint(
        self,
        tenant_id: UUID,
        instance_id: str
    ) -> Optional[str]:
        """
        获取实例端点URL
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            
        Returns:
            Optional[str]: 实例端点URL
        """
        # 这里应该从实例注册表或配置中获取端点
        # 暂时使用模拟数据
        
        # TODO: 实现实例注册表查询
        instance_endpoints = {
            "instance_1": "http://astrbot-instance-1:8080",
            "instance_2": "http://astrbot-instance-2:8080",
        }
        
        return instance_endpoints.get(instance_id)
    
    async def _get_instance_auth_token(
        self,
        tenant_id: UUID,
        instance_id: str
    ) -> Optional[str]:
        """
        获取实例认证Token
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            
        Returns:
            Optional[str]: 认证Token
        """
        try:
            # 查询租户配置中的实例认证信息
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if tenant and tenant.configuration:
                instance_tokens = tenant.configuration.get('instance_tokens', {})
                return instance_tokens.get(instance_id)
            
            return None
            
        except Exception as e:
            logger.error("get_instance_auth_token_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            return None
    
    async def _get_config_version(self, tenant_id: UUID) -> str:
        """
        获取配置版本号
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            str: 配置版本号
        """
        # 这里可以实现基于时间戳或递增序号的版本控制
        return datetime.utcnow().strftime("%Y%m%d%H%M%S")
    
    async def _get_tenant_instances(
        self,
        tenant_id: UUID,
        instance_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取租户的所有实例
        
        Args:
            tenant_id: 租户ID
            instance_filter: 实例过滤条件
            
        Returns:
            List[Dict[str, Any]]: 实例列表
        """
        # 这里应该从实例注册表查询
        # 暂时返回模拟数据
        
        # TODO: 实现实例注册表查询
        mock_instances = [
            {
                "instance_id": "instance_1",
                "endpoint": "http://astrbot-instance-1:8080",
                "status": "active",
                "platform": "qq"
            },
            {
                "instance_id": "instance_2", 
                "endpoint": "http://astrbot-instance-2:8080",
                "status": "active",
                "platform": "wechat"
            }
        ]
        
        # 应用过滤条件
        if instance_filter:
            filtered_instances = []
            for instance in mock_instances:
                match = True
                for key, value in instance_filter.items():
                    if instance.get(key) != value:
                        match = False
                        break
                if match:
                    filtered_instances.append(instance)
            return filtered_instances
        
        return mock_instances
    
    async def _get_tenant_base_config(self, tenant_id: UUID) -> Dict[str, Any]:
        """
        获取租户基础配置
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: 租户基础配置
        """
        try:
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # 构建基础配置
            base_config = {
                "tenant_name": tenant.name,
                "tenant_id": str(tenant.id),
                "webhook_url": f"https://saas-api.example.com/api/v1/webhooks/{tenant_id}",
                "api_base_url": "https://saas-api.example.com/api/v1",
                "features": {
                    "auto_reply": True,
                    "session_summary": True,
                    "agent_suggestions": True
                }
            }
            
            # 合并租户自定义配置
            if tenant.configuration:
                custom_config = tenant.configuration.get('astrbot_config', {})
                base_config.update(custom_config)
            
            return base_config
            
        except Exception as e:
            logger.error("get_tenant_base_config_error",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def _get_instance_specific_config(
        self,
        tenant_id: UUID,
        instance_id: str
    ) -> Dict[str, Any]:
        """
        获取实例特定配置
        
        Args:
            tenant_id: 租户ID
            instance_id: 实例ID
            
        Returns:
            Dict[str, Any]: 实例特定配置
        """
        try:
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if tenant and tenant.configuration:
                instance_configs = tenant.configuration.get('instance_configs', {})
                return instance_configs.get(instance_id, {})
            
            return {}
            
        except Exception as e:
            logger.error("get_instance_specific_config_error",
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        error=str(e))
            return {}
    
    async def _validate_config_updates(
        self,
        config_updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证配置更新
        
        Args:
            config_updates: 配置更新
            
        Returns:
            Dict[str, Any]: 验证后的配置更新
            
        Raises:
            ValueError: 配置验证失败
        """
        validated_updates = {}
        
        # 定义允许的配置字段和验证规则
        allowed_fields = {
            'webhook_url': str,
            'api_timeout': int,
            'max_message_length': int,
            'auto_reply_enabled': bool,
            'session_timeout': int,
            'log_level': str
        }
        
        for key, value in config_updates.items():
            if key in allowed_fields:
                expected_type = allowed_fields[key]
                if not isinstance(value, expected_type):
                    raise ValueError(f"Field '{key}' must be of type {expected_type.__name__}")
                
                # 特定字段的额外验证
                if key == 'log_level' and value not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                    raise ValueError(f"Invalid log_level: {value}")
                
                if key == 'api_timeout' and (value < 1 or value > 300):
                    raise ValueError("api_timeout must be between 1 and 300 seconds")
                
                validated_updates[key] = value
            else:
                logger.warning("unknown_config_field", field=key, value=value)
        
        return validated_updates
    
    async def _update_tenant_configuration(
        self,
        tenant_id: UUID,
        config_updates: Dict[str, Any]
    ) -> None:
        """
        更新租户配置到数据库
        
        Args:
            tenant_id: 租户ID
            config_updates: 配置更新
        """
        try:
            # 获取当前租户配置
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(stmt)
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            # 更新配置
            current_config = tenant.configuration or {}
            astrbot_config = current_config.get('astrbot_config', {})
            astrbot_config.update(config_updates)
            current_config['astrbot_config'] = astrbot_config
            
            # 保存到数据库
            tenant.configuration = current_config
            await self.db.commit()
            
        except Exception as e:
            await self.db.rollback()
            logger.error("update_tenant_configuration_error",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def close(self):
        """关闭HTTP客户端"""
        await self._http_client.aclose() 