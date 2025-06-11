"""
租户模型单元测试
测试Tenant模型的所有功能和业务逻辑
"""
import pytest
from datetime import datetime

from app.models.tenant import Tenant, TenantStatus, TenantPlan


class TestTenantModel:
    """租户模型测试类"""
    
    def test_tenant_creation(self):
        """测试租户基础创建"""
        tenant = Tenant(
            name="测试公司",
            email="test@example.com"
        )
        
        assert tenant.name == "测试公司"
        assert tenant.email == "test@example.com"
        assert tenant.status == TenantStatus.ACTIVE  # 默认状态
        assert tenant.plan == TenantPlan.BASIC       # 默认套餐
        assert tenant.metadata == {}                 # 默认空字典
        assert tenant.id is not None                 # 自动生成UUID
    
    def test_tenant_properties(self):
        """测试租户属性方法"""
        # 活跃租户
        active_tenant = Tenant(
            name="活跃公司",
            email="active@example.com",
            status=TenantStatus.ACTIVE
        )
        assert active_tenant.is_active is True
        assert active_tenant.display_name == "活跃公司"
        
        # 暂停租户
        suspended_tenant = Tenant(
            name="暂停公司", 
            email="suspended@example.com",
            status=TenantStatus.SUSPENDED
        )
        assert suspended_tenant.is_active is False
        
        # 无名称租户（使用邮箱）
        no_name_tenant = Tenant(
            name="",
            email="noname@example.com"
        )
        assert no_name_tenant.display_name == "noname"
    
    def test_status_methods(self):
        """测试状态管理方法"""
        tenant = Tenant(
            name="状态测试公司",
            email="status@example.com"
        )
        
        # 初始状态为活跃
        assert tenant.status == TenantStatus.ACTIVE
        
        # 暂停
        tenant.suspend()
        assert tenant.status == TenantStatus.SUSPENDED
        
        # 重新激活
        tenant.activate()
        assert tenant.status == TenantStatus.ACTIVE
        
        # 停用
        tenant.deactivate()
        assert tenant.status == TenantStatus.DEACTIVATED
    
    def test_metadata_operations(self):
        """测试元数据操作"""
        tenant = Tenant(
            name="元数据测试公司",
            email="metadata@example.com"
        )
        
        # 初始元数据为空
        assert tenant.get_metadata("industry") is None
        assert tenant.get_metadata("industry", "未知") == "未知"
        
        # 设置元数据
        tenant.update_metadata("industry", "科技")
        tenant.update_metadata("size", 100)
        
        assert tenant.get_metadata("industry") == "科技"
        assert tenant.get_metadata("size") == 100
        assert tenant.metadata == {"industry": "科技", "size": 100}
        
        # 更新现有元数据
        tenant.update_metadata("industry", "互联网")
        assert tenant.get_metadata("industry") == "互联网"
    
    def test_to_dict_method(self):
        """测试字典转换方法"""
        tenant = Tenant(
            name="字典测试公司",
            email="dict@example.com",
            plan=TenantPlan.PRO,
            api_key="test_api_key_123"
        )
        tenant.update_metadata("test_key", "test_value")
        
        # 不包含敏感信息
        basic_dict = tenant.to_dict(include_sensitive=False)
        assert basic_dict["name"] == "字典测试公司"
        assert basic_dict["email"] == "dict@example.com"
        assert basic_dict["plan"] == TenantPlan.PRO
        assert basic_dict["metadata"] == {"test_key": "test_value"}
        assert "api_key" not in basic_dict
        
        # 包含敏感信息
        sensitive_dict = tenant.to_dict(include_sensitive=True)
        assert sensitive_dict["api_key"] == "test_api_key_123"
    
    def test_api_key_generation(self):
        """测试API密钥生成"""
        api_key = Tenant.generate_api_key()
        
        # 验证格式
        assert api_key.startswith("ak_live_")
        assert len(api_key) > 20  # 确保有足够长度
        
        # 验证唯一性
        api_key2 = Tenant.generate_api_key()
        assert api_key != api_key2
    
    def test_string_representations(self):
        """测试字符串表示方法"""
        tenant = Tenant(
            name="字符串测试公司",
            email="string@example.com",
            status=TenantStatus.ACTIVE
        )
        
        # __str__ 方法
        str_repr = str(tenant)
        assert "字符串测试公司" in str_repr
        assert "active" in str_repr
        
        # __repr__ 方法（不应包含敏感信息）
        repr_str = repr(tenant)
        assert "Tenant" in repr_str
        assert "字符串测试公司" in repr_str
        assert tenant.email not in repr_str  # 邮箱不应在repr中
    
    def test_tenant_status_enum(self):
        """测试租户状态枚举"""
        assert TenantStatus.ACTIVE == "active"
        assert TenantStatus.SUSPENDED == "suspended"
        assert TenantStatus.DEACTIVATED == "deactivated"
    
    def test_tenant_plan_enum(self):
        """测试租户套餐枚举"""
        assert TenantPlan.BASIC == "basic"
        assert TenantPlan.PRO == "pro"
        assert TenantPlan.ENTERPRISE == "enterprise"
    
    def test_tenant_with_all_fields(self):
        """测试包含所有字段的租户创建"""
        metadata = {
            "industry": "电商",
            "company_size": "100-500人",
            "region": "上海"
        }
        
        tenant = Tenant(
            name="完整测试公司",
            email="complete@example.com",
            status=TenantStatus.ACTIVE,
            plan=TenantPlan.ENTERPRISE,
            api_key="ak_live_complete_test_123",
            metadata=metadata
        )
        
        assert tenant.name == "完整测试公司"
        assert tenant.email == "complete@example.com"
        assert tenant.status == TenantStatus.ACTIVE
        assert tenant.plan == TenantPlan.ENTERPRISE
        assert tenant.api_key == "ak_live_complete_test_123"
        assert tenant.metadata == metadata
        assert tenant.is_active is True
    
    def test_metadata_none_handling(self):
        """测试元数据为None的处理"""
        tenant = Tenant(
            name="空元数据测试公司",
            email="null_meta@example.com",
            metadata=None
        )
        
        # get_metadata应该正确处理None
        assert tenant.get_metadata("any_key") is None
        assert tenant.get_metadata("any_key", "default") == "default"
        
        # update_metadata应该创建字典
        tenant.update_metadata("new_key", "new_value")
        assert tenant.metadata == {"new_key": "new_value"}
    
    @pytest.mark.parametrize("status,expected_active", [
        (TenantStatus.ACTIVE, True),
        (TenantStatus.SUSPENDED, False),
        (TenantStatus.DEACTIVATED, False),
    ])
    def test_is_active_property(self, status, expected_active):
        """参数化测试is_active属性"""
        tenant = Tenant(
            name="状态参数化测试",
            email="param@example.com",
            status=status
        )
        assert tenant.is_active == expected_active 