"""
测试配置设置类
"""
import os
import pytest
from unittest.mock import patch
from pydantic_core import ValidationError

from app.core.config.settings import Settings


class TestSettings:
    """测试设置类"""
    
    def test_default_values(self):
        """测试默认配置值"""
        settings = Settings()
        
        # 基本应用配置
        assert settings.APP_NAME == "AstrBot SaaS Platform"
        assert settings.API_V1_STR == "/api/v1"
        assert settings.DEBUG is False
        assert settings.ENVIRONMENT == "development"
        
        # 服务器配置
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8000
        
        # 安全配置
        assert len(settings.SECRET_KEY) > 0  # 应该有默认的secret key
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        
        # 数据库配置默认值
        assert settings.DB_HOST == "localhost"
        assert settings.DB_PORT == 5432
        assert settings.DB_NAME == "astrbot_saas"
        assert settings.DB_USER == "postgres"
        
    @patch.dict(os.environ, {
        'APP_NAME': 'Test App',
        'DEBUG': 'true',
        'HOST': '127.0.0.1',
        'PORT': '9000',
        'SECRET_KEY': 'test-secret-key',
        'ACCESS_TOKEN_EXPIRE_MINUTES': '60',
        'DB_HOST': 'test-db',
        'DB_PORT': '3306',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass',
    })
    def test_environment_variable_override(self):
        """测试环境变量覆盖配置"""
        settings = Settings()
        
        # 验证环境变量被正确加载
        assert settings.APP_NAME == "Test App"
        assert settings.DEBUG is True
        assert settings.HOST == "127.0.0.1"
        assert settings.PORT == 9000
        assert settings.SECRET_KEY == "test-secret-key"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
        
        # 数据库配置
        assert settings.DB_HOST == "test-db"
        assert settings.DB_PORT == 3306
        assert settings.DB_NAME == "test_db"
        assert settings.DB_USER == "test_user"
        assert settings.DB_PASSWORD == "test_pass"
        
    def test_database_url_generation(self):
        """测试数据库URL生成"""
        with patch.dict(os.environ, {
            'DB_HOST': 'localhost',
            'DB_PORT': '5432',
            'DB_NAME': 'testdb',
            'DB_USER': 'testuser',
            'DB_PASSWORD': 'testpass',
        }):
            settings = Settings()
            expected_url = "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"
            assert settings.DATABASE_URL == expected_url
    
    def test_database_url_without_password(self):
        """测试没有密码时的数据库URL生成"""
        with patch.dict(os.environ, {
            'DB_HOST': 'localhost',
            'DB_PORT': '5432',
            'DB_NAME': 'testdb',
            'DB_USER': 'testuser',
            'DB_PASSWORD': '',  # 空密码
        }, clear=False):
            settings = Settings()
            expected_url = "postgresql+asyncpg://testuser@localhost:5432/testdb"
            assert settings.DATABASE_URL == expected_url
    
    @patch.dict(os.environ, {
        'REDIS_HOST': 'redis-server',
        'REDIS_PORT': '6380',
        'REDIS_PASSWORD': 'redis-pass',
        'REDIS_DB': '2',
    })
    def test_redis_url_generation(self):
        """测试Redis URL生成"""
        settings = Settings()
        expected_url = "redis://:redis-pass@redis-server:6380/2"
        assert settings.REDIS_URL == expected_url
    
    def test_cors_allowed_origins_parsing(self):
        """测试CORS允许源的解析"""
        with patch.dict(os.environ, {
            'CORS_ALLOWED_ORIGINS': 'http://localhost:3000,https://example.com,https://admin.example.com'
        }):
            settings = Settings()
            expected_origins = [
                "http://localhost:3000",
                "https://example.com", 
                "https://admin.example.com"
            ]
            assert settings.CORS_ALLOWED_ORIGINS == expected_origins
    
    def test_log_level_validation(self):
        """测试日志级别验证"""
        with patch.dict(os.environ, {'LOG_LEVEL': 'WARNING'}):
            settings = Settings()
            assert settings.LOG_LEVEL == "WARNING"
            
        with patch.dict(os.environ, {'LOG_LEVEL': 'invalid'}):
            settings = Settings()
            # 应该回退到默认值
            assert settings.LOG_LEVEL == "INFO"
    
    def test_settings_immutability(self):
        """测试设置的不可变性"""
        settings = Settings()
        
        # 尝试修改设置应该引发错误
        with pytest.raises(ValidationError):
            settings.APP_NAME = "Modified Name"
    
    def test_development_environment_defaults(self):
        """测试开发环境的默认配置"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
            settings = Settings()
            assert settings.ENVIRONMENT == "development"
            # 开发环境应该启用调试（如果DEBUG未明确设置）
    
    def test_production_environment_defaults(self):
        """测试生产环境的默认配置"""
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            settings = Settings()
            assert settings.ENVIRONMENT == "production"
            # 生产环境应该禁用调试
            assert settings.DEBUG is False
    
    def test_jwt_security_settings(self):
        """测试JWT安全配置"""
        settings = Settings()
        
        # 确保有加密算法配置
        assert hasattr(settings, 'ALGORITHM')
        
        # 确保token过期时间合理
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 1440  # 不超过24小时
    
    def test_sensitive_data_not_logged(self):
        """测试敏感数据不会被日志记录"""
        with patch.dict(os.environ, {
            'SECRET_KEY': 'super-secret-key',
            'DB_PASSWORD': 'super-secret-password',
        }):
            settings = Settings()
            
            # 转换为字符串不应该包含敏感信息
            settings_str = str(settings)
            assert 'super-secret-key' not in settings_str
            assert 'super-secret-password' not in settings_str 