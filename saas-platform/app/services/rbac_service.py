"""
RBAC权限管理服务

提供角色和权限的CRUD操作以及权限检查功能
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.role import Role, Permission, user_roles
from app.models.user import User
from app.models.tenant import Tenant

# 配置日志
logger = logging.getLogger(__name__)


class RBACService:
    """RBAC权限管理服务"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化RBAC服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    # 权限管理
    async def create_permission(
        self,
        name: str,
        description: str,
        resource: str,
        action: str
    ) -> Permission:
        """
        创建权限
        
        Args:
            name: 权限名称
            description: 权限描述  
            resource: 资源类型
            action: 操作类型
            
        Returns:
            Permission: 创建的权限
            
        Raises:
            ValueError: 权限已存在或参数无效
        """
        try:
            # 检查权限是否已存在
            stmt = select(Permission).where(Permission.name == name)
            existing = await self.db.execute(stmt)
            if existing.scalar_one_or_none():
                raise ValueError(f"Permission '{name}' already exists")
            
            # 创建权限
            permission = Permission(
                name=name,
                description=description,
                resource=resource,
                action=action
            )
            
            self.db.add(permission)
            await self.db.commit()
            await self.db.refresh(permission)
            
            logger.info("permission_created",
                       permission_id=permission.id,
                       name=name,
                       resource=resource,
                       action=action)
            
            return permission
            
        except Exception as e:
            await self.db.rollback()
            logger.error("create_permission_error",
                        name=name,
                        error=str(e))
            raise
    
    async def get_permission(self, permission_id: UUID) -> Optional[Permission]:
        """
        获取权限详情
        
        Args:
            permission_id: 权限ID
            
        Returns:
            Optional[Permission]: 权限对象
        """
        try:
            stmt = select(Permission).where(Permission.id == permission_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("get_permission_error",
                        permission_id=permission_id,
                        error=str(e))
            return None
    
    async def list_permissions(
        self,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        active_only: bool = True
    ) -> List[Permission]:
        """
        列出权限
        
        Args:
            resource: 过滤资源类型
            action: 过滤操作类型
            active_only: 只返回激活的权限
            
        Returns:
            List[Permission]: 权限列表
        """
        try:
            stmt = select(Permission)
            
            # 添加过滤条件
            conditions = []
            if resource:
                conditions.append(Permission.resource == resource)
            if action:
                conditions.append(Permission.action == action)
            if active_only:
                conditions.append(Permission.is_active == True)
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.order_by(Permission.resource, Permission.action)
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("list_permissions_error",
                        resource=resource,
                        action=action,
                        error=str(e))
            return []
    
    # 角色管理
    async def create_role(
        self,
        tenant_id: UUID,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        permission_ids: Optional[List[UUID]] = None,
        is_system_role: bool = False
    ) -> Role:
        """
        创建角色
        
        Args:
            tenant_id: 租户ID
            name: 角色名称
            display_name: 显示名称
            description: 角色描述
            permission_ids: 权限ID列表
            is_system_role: 是否为系统角色
            
        Returns:
            Role: 创建的角色
            
        Raises:
            ValueError: 角色已存在或参数无效
        """
        try:
            # 检查角色是否已存在
            stmt = select(Role).where(
                and_(
                    Role.tenant_id == tenant_id,
                    Role.name == name
                )
            )
            existing = await self.db.execute(stmt)
            if existing.scalar_one_or_none():
                raise ValueError(f"Role '{name}' already exists in tenant")
            
            # 创建角色
            role = Role(
                tenant_id=tenant_id,
                name=name,
                display_name=display_name,
                description=description,
                is_system_role=is_system_role
            )
            
            # 添加权限
            if permission_ids:
                permissions = await self._get_permissions_by_ids(permission_ids)
                role.permissions.extend(permissions)
            
            self.db.add(role)
            await self.db.commit()
            await self.db.refresh(role)
            
            logger.info("role_created",
                       tenant_id=tenant_id,
                       role_id=role.id,
                       name=name,
                       permissions_count=len(permission_ids or []))
            
            return role
            
        except Exception as e:
            await self.db.rollback()
            logger.error("create_role_error",
                        tenant_id=tenant_id,
                        name=name,
                        error=str(e))
            raise
    
    async def get_role(self, role_id: UUID, tenant_id: UUID) -> Optional[Role]:
        """
        获取角色详情
        
        Args:
            role_id: 角色ID
            tenant_id: 租户ID
            
        Returns:
            Optional[Role]: 角色对象
        """
        try:
            stmt = select(Role).options(
                selectinload(Role.permissions)
            ).where(
                and_(
                    Role.id == role_id,
                    Role.tenant_id == tenant_id
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("get_role_error",
                        role_id=role_id,
                        tenant_id=tenant_id,
                        error=str(e))
            return None
    
    async def list_roles(
        self,
        tenant_id: UUID,
        active_only: bool = True,
        include_system: bool = True
    ) -> List[Role]:
        """
        列出租户角色
        
        Args:
            tenant_id: 租户ID
            active_only: 只返回激活的角色
            include_system: 是否包含系统角色
            
        Returns:
            List[Role]: 角色列表
        """
        try:
            stmt = select(Role).options(
                selectinload(Role.permissions)
            ).where(Role.tenant_id == tenant_id)
            
            # 添加过滤条件
            if active_only:
                stmt = stmt.where(Role.is_active == True)
            if not include_system:
                stmt = stmt.where(Role.is_system_role == False)
            
            stmt = stmt.order_by(Role.is_system_role.desc(), Role.name)
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error("list_roles_error",
                        tenant_id=tenant_id,
                        error=str(e))
            return []
    
    async def update_role_permissions(
        self,
        role_id: UUID,
        tenant_id: UUID,
        permission_ids: List[UUID]
    ) -> Role:
        """
        更新角色权限
        
        Args:
            role_id: 角色ID
            tenant_id: 租户ID
            permission_ids: 新的权限ID列表
            
        Returns:
            Role: 更新后的角色
            
        Raises:
            ValueError: 角色不存在
        """
        try:
            # 获取角色
            role = await self.get_role(role_id, tenant_id)
            if not role:
                raise ValueError(f"Role {role_id} not found")
            
            # 获取新权限列表
            new_permissions = await self._get_permissions_by_ids(permission_ids)
            
            # 更新权限
            role.permissions.clear()
            role.permissions.extend(new_permissions)
            
            await self.db.commit()
            await self.db.refresh(role)
            
            logger.info("role_permissions_updated",
                       tenant_id=tenant_id,
                       role_id=role_id,
                       permissions_count=len(permission_ids))
            
            return role
            
        except Exception as e:
            await self.db.rollback()
            logger.error("update_role_permissions_error",
                        role_id=role_id,
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    # 用户角色管理
    async def assign_role_to_user(
        self,
        user_id: str,
        role_id: UUID,
        tenant_id: UUID,
        assigned_by: Optional[str] = None
    ) -> bool:
        """
        为用户分配角色
        
        Args:
            user_id: 用户ID
            role_id: 角色ID
            tenant_id: 租户ID
            assigned_by: 分配者用户ID
            
        Returns:
            bool: 是否成功分配
            
        Raises:
            ValueError: 用户或角色不存在
        """
        try:
            # 验证用户和角色存在
            user = await self._get_user(user_id, tenant_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            role = await self.get_role(role_id, tenant_id)
            if not role:
                raise ValueError(f"Role {role_id} not found")
            
            # 检查是否已分配
            if role in user.roles:
                logger.warning("role_already_assigned",
                              user_id=user_id,
                              role_id=role_id,
                              tenant_id=tenant_id)
                return True
            
            # 分配角色
            user.roles.append(role)
            await self.db.commit()
            
            logger.info("role_assigned_to_user",
                       user_id=user_id,
                       role_id=role_id,
                       tenant_id=tenant_id,
                       assigned_by=assigned_by)
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error("assign_role_to_user_error",
                        user_id=user_id,
                        role_id=role_id,
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    async def remove_role_from_user(
        self,
        user_id: str,
        role_id: UUID,
        tenant_id: UUID
    ) -> bool:
        """
        从用户移除角色
        
        Args:
            user_id: 用户ID
            role_id: 角色ID
            tenant_id: 租户ID
            
        Returns:
            bool: 是否成功移除
        """
        try:
            # 获取用户和角色
            user = await self._get_user(user_id, tenant_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # 查找并移除角色
            role_to_remove = None
            for role in user.roles:
                if role.id == role_id:
                    role_to_remove = role
                    break
            
            if role_to_remove:
                user.roles.remove(role_to_remove)
                await self.db.commit()
                
                logger.info("role_removed_from_user",
                           user_id=user_id,
                           role_id=role_id,
                           tenant_id=tenant_id)
                return True
            else:
                logger.warning("role_not_assigned_to_user",
                              user_id=user_id,
                              role_id=role_id,
                              tenant_id=tenant_id)
                return False
            
        except Exception as e:
            await self.db.rollback()
            logger.error("remove_role_from_user_error",
                        user_id=user_id,
                        role_id=role_id,
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    # 权限检查
    async def check_user_permission(
        self,
        user_id: str,
        tenant_id: UUID,
        resource: str,
        action: str
    ) -> bool:
        """
        检查用户权限
        
        Args:
            user_id: 用户ID
            tenant_id: 租户ID
            resource: 资源类型
            action: 操作类型
            
        Returns:
            bool: 是否有权限
        """
        try:
            user = await self._get_user_with_roles(user_id, tenant_id)
            if not user:
                return False
            
            return user.has_permission(resource, action)
            
        except Exception as e:
            logger.error("check_user_permission_error",
                        user_id=user_id,
                        tenant_id=tenant_id,
                        resource=resource,
                        action=action,
                        error=str(e))
            return False
    
    # 辅助方法
    async def _get_permissions_by_ids(self, permission_ids: List[UUID]) -> List[Permission]:
        """获取权限列表"""
        stmt = select(Permission).where(Permission.id.in_(permission_ids))
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def _get_user(self, user_id: str, tenant_id: UUID) -> Optional[User]:
        """获取用户"""
        stmt = select(User).where(
            and_(
                User.id == user_id,
                User.tenant_id == tenant_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _get_user_with_roles(self, user_id: str, tenant_id: UUID) -> Optional[User]:
        """获取用户及其角色"""
        stmt = select(User).options(
            selectinload(User.roles).selectinload(Role.permissions)
        ).where(
            and_(
                User.id == user_id,
                User.tenant_id == tenant_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def initialize_default_permissions(self) -> List[Permission]:
        """
        初始化默认权限
        
        Returns:
            List[Permission]: 创建的权限列表
        """
        default_permissions = [
            # 租户管理权限
            ("tenant:read", "查看租户信息", "tenant", "read"),
            ("tenant:write", "修改租户信息", "tenant", "write"),
            ("tenant:delete", "删除租户", "tenant", "delete"),
            
            # 用户管理权限
            ("user:read", "查看用户信息", "user", "read"),
            ("user:write", "修改用户信息", "user", "write"),
            ("user:delete", "删除用户", "user", "delete"),
            
            # 会话管理权限
            ("session:read", "查看会话", "session", "read"),
            ("session:write", "修改会话", "session", "write"),
            ("session:delete", "删除会话", "session", "delete"),
            
            # 消息管理权限
            ("message:read", "查看消息", "message", "read"),
            ("message:write", "发送消息", "message", "write"),
            ("message:delete", "删除消息", "message", "delete"),
            
            # 角色权限管理
            ("role:read", "查看角色", "role", "read"),
            ("role:write", "管理角色", "role", "write"),
            ("role:assign", "分配角色", "role", "assign"),
            
            # AI功能权限
            ("ai:use", "使用AI功能", "ai", "use"),
            ("ai:config", "配置AI功能", "ai", "config"),
            
            # 实例管理权限
            ("instance:read", "查看实例", "instance", "read"),
            ("instance:write", "管理实例", "instance", "write"),
            ("instance:config", "配置实例", "instance", "config"),
            
            # 数据分析权限
            ("analytics:read", "查看分析数据", "analytics", "read"),
            ("analytics:create", "创建分析报表", "analytics", "create"),
            ("analytics:export", "导出分析数据", "analytics", "export"),
        ]
        
        created_permissions = []
        
        for name, description, resource, action in default_permissions:
            try:
                # 检查权限是否已存在
                stmt = select(Permission).where(Permission.name == name)
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if not existing:
                    permission = await self.create_permission(name, description, resource, action)
                    created_permissions.append(permission)
                else:
                    created_permissions.append(existing)
                    
            except Exception as e:
                logger.error("initialize_default_permission_error",
                            name=name,
                            error=str(e))
        
        logger.info("default_permissions_initialized",
                   total_permissions=len(default_permissions),
                   created_count=len([p for p in created_permissions if p.id]))
        
        return created_permissions 