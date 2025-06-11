"""
RBAC权限管理数据模型

定义角色(Role)和权限(Permission)的数据模型
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.core.database import Base

# 角色-权限关联表
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', UUID(as_uuid=True), ForeignKey('permissions.id'), primary_key=True),
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)

# 用户-角色关联表
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', String(255), ForeignKey('users.id'), primary_key=True),
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id'), primary_key=True),
    Column('tenant_id', UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False),
    Column('assigned_at', DateTime(timezone=True), server_default=func.now()),
    Column('assigned_by', String(255), ForeignKey('users.id'), nullable=True)
)


class Permission(Base):
    """权限模型"""
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)  # 权限名称，如 "tenant:read"
    description = Column(Text, nullable=True)  # 权限描述
    resource = Column(String(50), nullable=False, index=True)  # 资源类型，如 "tenant", "session", "message"
    action = Column(String(50), nullable=False, index=True)  # 操作类型，如 "read", "write", "delete"
    is_active = Column(Boolean, default=True, nullable=False)  # 权限是否激活
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 反向关系
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission(name={self.name}, resource={self.resource}, action={self.action})>"


class Role(Base):
    """角色模型"""
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, index=True)  # 角色名称，如 "admin", "agent", "viewer"
    display_name = Column(String(100), nullable=False)  # 显示名称，如 "管理员", "客服代表"
    description = Column(Text, nullable=True)  # 角色描述
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    is_system_role = Column(Boolean, default=False, nullable=False)  # 是否为系统预置角色
    is_active = Column(Boolean, default=True, nullable=False)  # 角色是否激活
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    tenant = relationship("Tenant", back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users = relationship(
        "User", 
        secondary=user_roles, 
        back_populates="roles",
        primaryjoin="Role.id == user_roles.c.role_id",
        secondaryjoin="User.id == user_roles.c.user_id"
    )
    
    def __repr__(self):
        return f"<Role(name={self.name}, tenant_id={self.tenant_id})>"
    
    def has_permission(self, resource: str, action: str) -> bool:
        """
        检查角色是否具有特定权限
        
        Args:
            resource: 资源类型
            action: 操作类型
            
        Returns:
            bool: 是否有权限
        """
        if not self.is_active:
            return False
        
        for permission in self.permissions:
            if (permission.is_active and 
                permission.resource == resource and 
                permission.action == action):
                return True
        
        return False
    
    def get_permissions_list(self) -> list:
        """
        获取角色的所有权限列表
        
        Returns:
            list: 权限列表
        """
        return [
            {
                "id": str(permission.id),
                "name": permission.name,
                "resource": permission.resource,
                "action": permission.action,
                "description": permission.description
            }
            for permission in self.permissions
            if permission.is_active
        ] 