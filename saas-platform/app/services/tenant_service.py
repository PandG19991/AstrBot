"""
租户管理服务层
实现租户的CRUD操作、配置管理和业务逻辑
"""

from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status, Depends

from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import (
    TenantCreate, 
    TenantRead, 
    TenantUpdate
)
from app.core.database import get_db
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TenantService:
    """租户管理服务"""
    
    def __init__(self, db: AsyncSession):
        """初始化租户服务
        
        Args:
            db: 数据库异步会话
        """
        self.db = db
    
    async def create_tenant(self, tenant_data: TenantCreate) -> TenantRead:
        """创建新租户
        
        Args:
            tenant_data: 租户创建数据
            
        Returns:
            TenantRead: 创建的租户信息
            
        Raises:
            HTTPException: 当邮箱或企业名称已存在时
        """
        try:
            # 1. 检查邮箱唯一性
            existing_tenant = await self._get_tenant_by_email(tenant_data.contact_email)
            if existing_tenant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被其他租户使用"
                )
            
            # 2. 检查企业名称唯一性
            existing_name = await self._get_tenant_by_name(tenant_data.name)
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="企业名称已存在"
                )
            
            # 3. 创建租户记录
            tenant = Tenant(
                id=uuid4(),
                name=tenant_data.name,
                display_name=tenant_data.display_name,
                contact_email=tenant_data.contact_email,
                contact_phone=tenant_data.contact_phone,
                description=tenant_data.description,
                industry=tenant_data.industry,
                company_size=tenant_data.company_size,
                subscription_plan=tenant_data.subscription_plan,
                is_active=True
            )
            
            self.db.add(tenant)
            await self.db.commit()
            await self.db.refresh(tenant)
            
            logger.info(
                "租户创建成功",
                tenant_id=str(tenant.id),
                tenant_name=tenant.name,
                contact_email=tenant.contact_email
            )
            
            return TenantRead.model_validate(tenant)
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "租户创建失败",
                error=str(e),
                tenant_data=tenant_data.model_dump()
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="租户创建失败，请稍后重试"
            )
    
    async def get_tenant(self, tenant_id: UUID) -> Optional[TenantRead]:
        """根据ID获取租户信息
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            Optional[TenantRead]: 租户信息，不存在则返回None
        """
        try:
            query = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(query)
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                return None
                
            return TenantRead.model_validate(tenant)
            
        except Exception as e:
            logger.error(
                "获取租户信息失败",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取租户信息失败"
            )
    
    async def get_tenant_by_id_with_verification(self, tenant_id: UUID) -> TenantRead:
        """获取租户信息并验证存在性
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            TenantRead: 租户信息
            
        Raises:
            HTTPException: 当租户不存在时
        """
        tenant = await self.get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        return tenant
    
    async def update_tenant(self, tenant_id: UUID, tenant_data: TenantUpdate) -> TenantRead:
        """更新租户信息
        
        Args:
            tenant_id: 租户ID
            tenant_data: 更新数据
            
        Returns:
            TenantRead: 更新后的租户信息
            
        Raises:
            HTTPException: 当租户不存在或更新失败时
        """
        try:
            # 1. 获取现有租户
            query = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(query)
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="租户不存在"
                )
            
            # 2. 检查邮箱唯一性（如果邮箱有变更）
            if tenant_data.contact_email and tenant_data.contact_email != tenant.contact_email:
                existing_tenant = await self._get_tenant_by_email(tenant_data.contact_email)
                if existing_tenant:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="邮箱已被其他租户使用"
                    )
            
            # 3. 更新字段
            update_data = tenant_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(tenant, field, value)
            
            await self.db.commit()
            await self.db.refresh(tenant)
            
            logger.info(
                "租户信息更新成功",
                tenant_id=str(tenant_id),
                updated_fields=list(update_data.keys())
            )
            
            return TenantRead.model_validate(tenant)
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "租户更新失败",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="租户更新失败"
            )
    
    async def delete_tenant(self, tenant_id: UUID) -> bool:
        """删除租户
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            bool: 删除是否成功
            
        Raises:
            HTTPException: 当租户不存在或删除失败时
        """
        try:
            # 1. 检查租户是否存在
            query = select(Tenant).where(Tenant.id == tenant_id)
            result = await self.db.execute(query)
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="租户不存在"
                )
            
            # 2. 检查是否有关联用户（软删除保护）
            user_count = await self._count_tenant_users(tenant_id)
            if user_count > 0:
                # 执行软删除
                tenant.is_active = False
                tenant.deleted_at = func.now()
                await self.db.commit()
                
                logger.info(
                    "租户软删除成功",
                    tenant_id=str(tenant_id),
                    user_count=user_count
                )
            else:
                # 执行硬删除
                await self.db.delete(tenant)
                await self.db.commit()
                
                logger.info(
                    "租户硬删除成功",
                    tenant_id=str(tenant_id)
                )
            
            return True
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(
                "租户删除失败",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="租户删除失败"
            )
    
    async def list_tenants(
        self, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[TenantRead]:
        """获取租户列表（管理员功能）
        
        Args:
            skip: 跳过数量
            limit: 限制数量
            search: 搜索关键词
            is_active: 是否激活状态过滤
            
        Returns:
            List[TenantRead]: 租户列表
        """
        try:
            query = select(Tenant)
            
            # 添加搜索条件
            if search:
                search_pattern = f"%{search}%"
                query = query.where(
                    or_(
                        Tenant.name.ilike(search_pattern),
                        Tenant.display_name.ilike(search_pattern),
                        Tenant.contact_email.ilike(search_pattern)
                    )
                )
            
            # 添加状态过滤
            if is_active is not None:
                query = query.where(Tenant.is_active == is_active)
            
            # 添加分页
            query = query.offset(skip).limit(limit).order_by(Tenant.created_at.desc())
            
            result = await self.db.execute(query)
            tenants = result.scalars().all()
            
            return [TenantRead.model_validate(tenant) for tenant in tenants]
            
        except Exception as e:
            logger.error(
                "获取租户列表失败",
                error=str(e),
                skip=skip,
                limit=limit,
                search=search
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取租户列表失败"
            )
    
    async def get_tenant_statistics(self, tenant_id: UUID) -> Dict[str, Any]:
        """获取租户统计信息
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            # 验证租户存在
            await self.get_tenant_by_id_with_verification(tenant_id)
            
            # 统计用户数量
            user_count = await self._count_tenant_users(tenant_id)
            
            # TODO: 添加更多统计信息
            # - 会话数量
            # - 消息数量
            # - 存储使用量
            # - 活跃度指标
            
            return {
                "tenant_id": str(tenant_id),
                "user_count": user_count,
                "sessions_count": 0,  # 待实现
                "messages_count": 0,  # 待实现
                "storage_usage": 0,   # 待实现
                "last_activity": None  # 待实现
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "获取租户统计失败",
                tenant_id=str(tenant_id),
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取租户统计失败"
            )
    
    # 私有辅助方法
    async def _get_tenant_by_email(self, email: str) -> Optional[Tenant]:
        """根据邮箱获取租户"""
        query = select(Tenant).where(Tenant.contact_email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_tenant_by_name(self, name: str) -> Optional[Tenant]:
        """根据名称获取租户"""
        query = select(Tenant).where(Tenant.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def _count_tenant_users(self, tenant_id: UUID) -> int:
        """统计租户用户数量"""
        query = select(func.count(User.id)).where(User.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return result.scalar() or 0


# 依赖注入函数
async def get_tenant_service(db: AsyncSession = Depends(get_db)) -> TenantService:
    """获取租户服务实例"""
    return TenantService(db) 