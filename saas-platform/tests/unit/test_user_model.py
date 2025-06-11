"""
用户模型单元测试
测试User模型的所有功能，特别是复合主键和多租户隔离
"""
import pytest
import uuid
from datetime import datetime

from app.models.user import User
from app.models.tenant import Tenant, TenantStatus


class TestUserModel:
    """用户模型测试类"""
    
    def test_user_creation_basic(self):
        """测试用户基础创建"""
        tenant_id = uuid.uuid4()
        platform = "qq_official"
        user_id = "123456789"
        
        user = User(
            id=User.create_user_id(platform, user_id),
            tenant_id=tenant_id,
            platform=platform,
            user_id=user_id,
            nickname="测试用户"
        )
        
        assert user.id == "qq_official:123456789"
        assert user.tenant_id == tenant_id
        assert user.platform == platform
        assert user.user_id == user_id
        assert user.nickname == "测试用户"
        assert user.extra_data == {}
    
    def test_composite_user_id_creation(self):
        """测试复合用户ID创建"""
        # 测试create_user_id方法
        user_id = User.create_user_id("wechat", "user_abc123")
        assert user_id == "wechat:user_abc123"
        
        # 测试不同平台
        qq_id = User.create_user_id("qq_official", "123456789")
        assert qq_id == "qq_official:123456789"
        
        telegram_id = User.create_user_id("telegram", "user_telegram")
        assert telegram_id == "telegram:user_telegram"
    
    def test_composite_user_id_parsing(self):
        """测试复合用户ID解析"""
        # 正常解析
        platform, user_id = User.parse_user_id("qq_official:123456789")
        assert platform == "qq_official"
        assert user_id == "123456789"
        
        # 包含冒号的用户ID
        platform, user_id = User.parse_user_id("wechat:user:with:colons")
        assert platform == "wechat"
        assert user_id == "user:with:colons"
        
        # 错误格式测试
        with pytest.raises(ValueError, match="Invalid user ID format"):
            User.parse_user_id("invalid_format")
        
        with pytest.raises(ValueError, match="Invalid user ID format"):
            User.parse_user_id("")
    
    def test_user_properties(self):
        """测试用户属性方法"""
        tenant_id = uuid.uuid4()
        
        # 有昵称的用户
        user_with_nickname = User(
            id="qq_official:123456789",
            tenant_id=tenant_id,
            platform="qq_official",
            user_id="123456789",
            nickname="小明"
        )
        assert user_with_nickname.display_name == "小明"
        assert user_with_nickname.platform_user_id == "123456789"
        
        # 无昵称的用户
        user_without_nickname = User(
            id="wechat:user_abc",
            tenant_id=tenant_id,
            platform="wechat",
            user_id="user_abc"
        )
        assert user_without_nickname.display_name == "user_abc"
    
    def test_metadata_operations(self):
        """测试元数据操作"""
        tenant_id = uuid.uuid4()
        user = User(
            id="telegram:user123",
            tenant_id=tenant_id,
            platform="telegram", 
            user_id="user123"
        )
        
        # 初始元数据为空
        assert user.get_metadata("avatar_url") is None
        assert user.get_metadata("avatar_url", "default.jpg") == "default.jpg"
        
        # 设置元数据
        user.update_metadata("avatar_url", "https://example.com/avatar.jpg")
        user.update_metadata("last_active", "2024-01-01T10:00:00Z")
        
        assert user.get_metadata("avatar_url") == "https://example.com/avatar.jpg"
        assert user.get_metadata("last_active") == "2024-01-01T10:00:00Z"
        assert user.extra_data == {
            "avatar_url": "https://example.com/avatar.jpg",
            "last_active": "2024-01-01T10:00:00Z"
        }
    
    def test_nickname_update(self):
        """测试昵称更新"""
        tenant_id = uuid.uuid4()
        user = User(
            id="qq_official:123456789",
            tenant_id=tenant_id,
            platform="qq_official",
            user_id="123456789"
        )
        
        # 设置昵称
        user.update_nickname("新昵称")
        assert user.nickname == "新昵称"
        
        # 测试长度限制
        long_nickname = "a" * 150  # 超过100字符限制
        user.update_nickname(long_nickname)
        assert len(user.nickname) == 100
        assert user.nickname == "a" * 100
        
        # 清空昵称
        user.update_nickname("")
        assert user.nickname is None
        
        user.update_nickname(None)
        assert user.nickname is None
    
    def test_platform_user_matching(self):
        """测试平台用户匹配"""
        tenant_id = uuid.uuid4()
        user = User(
            id="qq_official:123456789",
            tenant_id=tenant_id,
            platform="qq_official",
            user_id="123456789",
            nickname="测试用户"
        )
        
        # 匹配测试
        assert user.is_same_platform_user("qq_official", "123456789") is True
        assert user.is_same_platform_user("wechat", "123456789") is False
        assert user.is_same_platform_user("qq_official", "987654321") is False
        assert user.is_same_platform_user("wechat", "987654321") is False
    
    def test_to_dict_method(self):
        """测试字典转换方法"""
        tenant_id = uuid.uuid4()
        user = User(
            id="wechat:user_abc123",
            tenant_id=tenant_id,
            platform="wechat",
            user_id="user_abc123",
            nickname="测试用户"
        )
        user.update_metadata("avatar_url", "https://example.com/avatar.jpg")
        
        # 包含元数据
        full_dict = user.to_dict(include_metadata=True)
        assert full_dict["id"] == "wechat:user_abc123"
        assert full_dict["tenant_id"] == str(tenant_id)
        assert full_dict["platform"] == "wechat"
        assert full_dict["user_id"] == "user_abc123"
        assert full_dict["nickname"] == "测试用户"
        assert full_dict["display_name"] == "测试用户"
        assert full_dict["metadata"] == {"avatar_url": "https://example.com/avatar.jpg"}
        
        # 不包含元数据
        basic_dict = user.to_dict(include_metadata=False)
        assert "metadata" not in basic_dict or basic_dict["metadata"] is None
    
    def test_string_representations(self):
        """测试字符串表示方法"""
        tenant_id = uuid.uuid4()
        
        # 有昵称的用户
        user_with_nickname = User(
            id="qq_official:123456789",
            tenant_id=tenant_id,
            platform="qq_official",
            user_id="123456789",
            nickname="小明"
        )
        
        str_repr = str(user_with_nickname)
        assert "小明@qq_official" == str_repr
        
        repr_str = repr(user_with_nickname)
        assert "User" in repr_str
        assert "qq_official:123456789" in repr_str
        assert "qq_official" in repr_str
        
        # 无昵称的用户
        user_without_nickname = User(
            id="telegram:user123",
            tenant_id=tenant_id,
            platform="telegram",
            user_id="user123"
        )
        
        str_repr = str(user_without_nickname)
        assert "user123@telegram" == str_repr
    
    def test_metadata_none_handling(self):
        """测试元数据为None的处理"""
        tenant_id = uuid.uuid4()
        user = User(
            id="qq_official:123456789",
            tenant_id=tenant_id,
            platform="qq_official",
            user_id="123456789",
            extra_data=None
        )
        
        # get_metadata应该正确处理None
        assert user.get_metadata("any_key") is None
        assert user.get_metadata("any_key", "default") == "default"
        
        # update_metadata应该创建字典
        user.update_metadata("new_key", "new_value")
        assert user.extra_data == {"new_key": "new_value"}
    
    def test_user_with_different_platforms(self):
        """测试不同平台的用户创建"""
        tenant_id = uuid.uuid4()
        
        platforms_data = [
            ("qq_official", "123456789", "QQ用户"),
            ("wechat", "wx_user_123", "微信用户"),
            ("telegram", "tg_user_456", "Telegram用户"),
            ("dingtalk", "dt_user_789", "钉钉用户"),
            ("lark", "lk_user_abc", "飞书用户"),
        ]
        
        users = []
        for platform, user_id, nickname in platforms_data:
            composite_id = User.create_user_id(platform, user_id)
            user = User(
                id=composite_id,
                tenant_id=tenant_id,
                platform=platform,
                user_id=user_id,
                nickname=nickname
            )
            users.append(user)
            
            # 验证复合ID格式
            assert user.id == f"{platform}:{user_id}"
            assert user.platform == platform
            assert user.user_id == user_id
            assert user.nickname == nickname
        
        # 验证所有用户都属于同一租户
        assert all(user.tenant_id == tenant_id for user in users)
        
        # 验证用户ID的唯一性
        user_ids = [user.id for user in users]
        assert len(user_ids) == len(set(user_ids))
    
    @pytest.mark.parametrize("platform,user_id,expected_composite", [
        ("qq_official", "123456789", "qq_official:123456789"),
        ("wechat", "user_abc", "wechat:user_abc"),
        ("telegram", "user:with:colons", "telegram:user:with:colons"),
        ("custom_platform", "special_user_123", "custom_platform:special_user_123"),
    ])
    def test_user_id_creation_parametrized(self, platform, user_id, expected_composite):
        """参数化测试用户ID创建"""
        composite_id = User.create_user_id(platform, user_id)
        assert composite_id == expected_composite
        
        # 验证解析的一致性
        parsed_platform, parsed_user_id = User.parse_user_id(composite_id)
        assert parsed_platform == platform
        assert parsed_user_id == user_id 