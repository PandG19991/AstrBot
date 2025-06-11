"""
租户数据模型
对应数据库 tenants 表，是多租户架构的核心实体
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, String, Enum as SQLEnum, Text, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TenantStatus(str, Enum):
    """租户状态枚举"""
    ACTIVE = "active"         # 活跃
    SUSPENDED = "suspended"   # 暂停
    DEACTIVATED = "deactivated"  # 停用


class TenantPlan(str, Enum):
    """租户套餐枚举"""
    BASIC = "basic"           # 基础版
    PRO = "pro"              # 专业版
    ENTERPRISE = "enterprise" # 企业版


class Tenant(Base):
    """
    租户模型
    
    参考:
    - @cursor doc/database_design/erd_diagram.md TENANTS表
    - @cursor doc/api_contracts/models/common_models.yaml TenantEntity
    """
    __tablename__ = "tenants"
    
    # 主键
    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        comment="租户唯一标识"
    )
    
    # 基本信息
    name = Column(
        String(100), 
        nullable=False,
        comment="租户名称"
    )
    
    email = Column(
        String(255), 
        nullable=False, 
        unique=True,
        comment="管理员邮箱"
    )
    
    # 状态和套餐
    status = Column(
        SQLEnum(
            TenantStatus.ACTIVE,
            TenantStatus.SUSPENDED, 
            TenantStatus.DEACTIVATED,
            name="tenant_status"
        ),
        nullable=False,
        default=TenantStatus.ACTIVE,
        comment="租户状态"
    )
    
    plan = Column(
        SQLEnum(
            TenantPlan.BASIC,
            TenantPlan.PRO,
            TenantPlan.ENTERPRISE,
            name="tenant_plan"
        ),
        nullable=False,
        default=TenantPlan.BASIC,
        comment="租户套餐"
    )
    
    # API访问
    api_key = Column(
        String(128),
        unique=True,
        nullable=True,
        comment="API访问密钥"
    )
    
    # 扩展字段
    extra_data = Column(
        JSON,
        nullable=True,
        default=lambda: {},
        comment="扩展元数据"
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
    
    # 关系定义 (需要其他模型创建后启用)
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="tenant", cascade="all, delete-orphan")
    # configs = relationship("TenantConfig", back_populates="tenant", cascade="all, delete-orphan")
    
    # RBAC角色关系
    roles = relationship("Role", back_populates="tenant", cascade="all, delete-orphan")
    
    # 表级约束和索引
    __table_args__ = (
        # 邮箱唯一索引
        Index('ix_tenant_email', 'email'),
        # 状态索引（查询活跃租户）
        Index('ix_tenant_status', 'status'),
        # API Key索引
        Index('ix_tenant_api_key', 'api_key'),
        # 创建时间索引
        Index('ix_tenant_created_at', 'created_at'),
        
        # 表注释
        {"comment": "租户表 - 多租户架构的核心实体"}
    )
    
    def __init__(self, **kwargs):
        """初始化方法，支持metadata参数"""
        # 处理metadata参数，映射到extra_data
        if 'metadata' in kwargs:
            kwargs['extra_data'] = kwargs.pop('metadata')
        
        # 设置默认值（SQLAlchemy不会在对象创建时自动应用）
        if 'id' not in kwargs:
            kwargs['id'] = uuid.uuid4()
        if 'status' not in kwargs:
            kwargs['status'] = TenantStatus.ACTIVE
        if 'plan' not in kwargs:
            kwargs['plan'] = TenantPlan.BASIC
        if 'extra_data' not in kwargs:
            kwargs['extra_data'] = {}
            
        super().__init__(**kwargs)
    
    def __setattr__(self, name, value):
        """处理metadata属性的设置"""
        if name == 'metadata':
            # 将metadata映射到extra_data
            super().__setattr__('extra_data', value)
        else:
            super().__setattr__(name, value)
    
    def __getattribute__(self, name):
        """处理metadata属性的获取"""
        if name == 'metadata':
            # 返回extra_data的值
            extra_data = super().__getattribute__('extra_data')
            return extra_data or {}
        else:
            return super().__getattribute__(name)
    
    def __repr__(self) -> str:
        """字符串表示，不包含敏感信息"""
        return f"<Tenant(id={self.id}, name='{self.name}', status='{self.status}')>"
    
    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"{self.name} ({self.status.value})"
    
    @property
    def is_active(self) -> bool:
        """检查租户是否处于活跃状态"""
        return self.status == TenantStatus.ACTIVE
    
    @property
    def display_name(self) -> str:
        """显示名称，优先使用name，fallback到email"""
        return self.name or self.email.split('@')[0]
    
    @property
    def tenant_metadata(self) -> Dict[str, Any]:
        """元数据属性，兼容API和测试"""
        return self.extra_data or {}
    
    # 为了兼容测试，提供metadata别名
    def get_metadata_dict(self) -> Dict[str, Any]:
        """获取元数据字典"""
        return self.extra_data or {}
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Args:
            include_sensitive: 是否包含敏感信息（如API密钥）
            
        Returns:
            Dict[str, Any]: 租户信息字典
        """
        data = {
            "id": str(self.id),
            "name": self.name,
            "email": self.email,
            "status": self.status,
            "plan": self.plan,
            "metadata": self.extra_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive and self.api_key:
            data["api_key"] = self.api_key
            
        return data
    
    @classmethod
    def generate_api_key(cls) -> str:
        """
        生成API密钥
        
        Returns:
            str: 格式化的API密钥
        """
        import secrets
        return f"ak_live_{secrets.token_urlsafe(32)}"
    
    def activate(self) -> None:
        """激活租户"""
        self.status = TenantStatus.ACTIVE
        
    def suspend(self) -> None:
        """暂停租户"""
        self.status = TenantStatus.SUSPENDED
        
    def deactivate(self) -> None:
        """停用租户"""
        self.status = TenantStatus.DEACTIVATED
    
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
        获取元数据值
        
        Args:
            key: 元数据键
            default: 默认值
            
        Returns:
            Any: 元数据值
        """
        if self.extra_data is None:
            return default
        return self.extra_data.get(key, default) 