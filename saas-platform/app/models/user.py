"""
用户数据模型
对应数据库 users 表，管理多平台用户信息
"""
from datetime import datetime
from typing import Any, Dict, Optional, List

from sqlalchemy import Column, String, DateTime, JSON, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    """
    用户模型
    
    注意: 用户ID是复合主键格式 "platform:user_id"
    支持跨平台用户统一管理，同时确保租户隔离
    
    参考:
    - @cursor doc/database_design/erd_diagram.md USERS表
    - @cursor doc/api_contracts/models/common_models.yaml UserEntity
    """
    __tablename__ = "users"
    
    # 复合主键：platform:user_id格式
    id = Column(
        String(255), 
        primary_key=True,
        comment="用户唯一标识，格式：platform:user_id"
    )
    
    # 🚨 多租户隔离字段 - CRITICAL
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属租户ID"
    )
    
    # 平台和用户信息
    platform = Column(
        String(50),
        nullable=False,
        comment="来源平台类型"
    )
    
    user_id = Column(
        String(200),
        nullable=False, 
        comment="平台内用户ID"
    )
    
    nickname = Column(
        String(100),
        nullable=True,
        comment="用户昵称"
    )
    
    # 扩展字段
    extra_data = Column(
        JSON,
        nullable=True,
        default=lambda: {},
        comment="平台特定的扩展数据"
    )
    
    # 时间戳字段
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="最后更新时间"
    )
    
    # 关系定义
    tenant = relationship("Tenant", back_populates="users")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    # messages = relationship("Message", back_populates="user")
    
    # RBAC角色关系
    roles = relationship(
        "Role", 
        secondary="user_roles", 
        back_populates="users",
        primaryjoin="User.id == user_roles.c.user_id",
        secondaryjoin="Role.id == user_roles.c.role_id"
    )
    
    # 表级约束和索引
    __table_args__ = (
        # 租户+平台+用户ID的唯一约束
        Index('ix_user_tenant_platform_user', 'tenant_id', 'platform', 'user_id', unique=True),
        # 租户ID索引 (多租户隔离查询)
        Index('ix_user_tenant_id', 'tenant_id'),
        # 平台索引
        Index('ix_user_platform', 'platform'),
        # 创建时间索引
        Index('ix_user_created_at', 'created_at'),
        # 昵称搜索索引
        Index('ix_user_nickname', 'nickname'),
        
        # 表注释
        {"comment": "用户表 - 多平台用户统一管理，确保租户隔离"}
    )
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<User(id='{self.id}', tenant_id={self.tenant_id}, platform='{self.platform}')>"
    
    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"{self.nickname or self.user_id}@{self.platform}"
    
    @property
    def display_name(self) -> str:
        """显示名称，优先使用昵称"""
        return self.nickname or self.user_id or self.id
    
    @property 
    def platform_user_id(self) -> str:
        """获取平台用户ID部分"""
        return self.user_id
    
    def __init__(self, **kwargs):
        """初始化用户，设置默认值"""
        # 确保extra_data有默认值
        if 'extra_data' not in kwargs or kwargs['extra_data'] is None:
            kwargs['extra_data'] = {}
        super().__init__(**kwargs)
    
    @classmethod
    def create_user_id(cls, platform: str, user_id: str) -> str:
        """
        创建复合用户ID
        
        Args:
            platform: 平台类型
            user_id: 平台内用户ID
            
        Returns:
            str: 格式化的复合用户ID
        """
        return f"{platform}:{user_id}"
    
    @classmethod
    def parse_user_id(cls, composite_id: str) -> tuple[str, str]:
        """
        解析复合用户ID
        
        Args:
            composite_id: 复合用户ID
            
        Returns:
            tuple[str, str]: (platform, user_id)
            
        Raises:
            ValueError: 格式不正确时抛出异常
        """
        if ":" not in composite_id:
            raise ValueError(f"Invalid user ID format: {composite_id}")
        
        parts = composite_id.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid user ID format: {composite_id}")
            
        return parts[0], parts[1]
    
    def to_dict(self, include_metadata: bool = True) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Args:
            include_metadata: 是否包含元数据
            
        Returns:
            Dict[str, Any]: 用户信息字典
        """
        data = {
            "id": self.id,
            "tenant_id": str(self.tenant_id),
            "platform": self.platform,
            "user_id": self.user_id,
            "nickname": self.nickname,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_metadata:
            data["metadata"] = self.extra_data or {}
            
        return data
    
    def update_metadata(self, key: str, value: Any) -> None:
        """
        更新元数据
        
        Args:
            key: 元数据键
            value: 元数据值
        """
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        获取元数据
        
        Args:
            key: 元数据键
            default: 默认值
            
        Returns:
            Any: 元数据值
        """
        if self.extra_data is None:
            return default
        return self.extra_data.get(key, default)
    
    def update_nickname(self, nickname: str) -> None:
        """
        更新用户昵称
        
        Args:
            nickname: 新昵称
        """
        # 空字符串和None都设置为None
        if not nickname:
            self.nickname = None
            return
        
        # 截断到100字符以符合数据库约束
        if len(nickname) > 100:
            nickname = nickname[:100]
        self.nickname = nickname
    
    def is_same_platform_user(self, platform: str, user_id: str) -> bool:
        """
        检查是否为同一平台用户
        
        Args:
            platform: 平台类型
            user_id: 平台用户ID
            
        Returns:
            bool: 是否为同一用户
        """
        return self.platform == platform and self.user_id == user_id

    # RBAC权限方法
    def has_permission(self, resource: str, action: str) -> bool:
        """
        检查用户是否具有特定权限
        
        Args:
            resource: 资源类型
            action: 操作类型
            
        Returns:
            bool: 是否有权限
        """
        for role in self.roles:
            if role.is_active and role.has_permission(resource, action):
                return True
        return False
    
    def get_all_permissions(self) -> List[Dict[str, Any]]:
        """
        获取用户的所有权限列表
        
        Returns:
            List[Dict[str, Any]]: 权限列表
        """
        permissions = []
        seen_permissions = set()
        
        for role in self.roles:
            if role.is_active:
                for permission in role.get_permissions_list():
                    permission_key = f"{permission['resource']}:{permission['action']}"
                    if permission_key not in seen_permissions:
                        permissions.append({
                            **permission,
                            "role": role.name,
                            "role_display_name": role.display_name
                        })
                        seen_permissions.add(permission_key)
        
        return permissions
    
    def get_roles_list(self) -> List[Dict[str, Any]]:
        """
        获取用户的角色列表
        
        Returns:
            List[Dict[str, Any]]: 角色列表
        """
        return [
            {
                "id": str(role.id),
                "name": role.name,
                "display_name": role.display_name,
                "description": role.description,
                "is_system_role": role.is_system_role,
                "permissions_count": len(role.permissions)
            }
            for role in self.roles
            if role.is_active
        ]


def update_tenant_relationships():
    """
    更新租户模型关系
    这个函数在导入后被调用以避免循环导入
    """
    from app.models.tenant import Tenant
    # 确保租户模型有用户关系
    if not hasattr(Tenant, 'users'):
        Tenant.users = relationship("User", back_populates="tenant") 