"""
测试配置和通用fixtures
"""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.config.settings import get_settings
from app.core.database import Base, get_db

# 测试数据库配置 - 使用内存数据库
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# 创建测试引擎 - 关键修复：确保所有连接共享同一个数据库
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
    echo=True,  # 调试时可查看SQL语句
)

# 创建测试会话工厂
TestingSessionLocal = sessionmaker(
    test_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建测试事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_test_db():
    """设置测试数据库"""
    # 关键修复：强制替换应用程序的数据库引擎
    from app.core import database
    
    # 保存原始引擎
    original_engine = database.engine
    original_sessionlocal = database.AsyncSessionLocal
    
    # 替换为测试引擎
    database.engine = test_engine
    database.AsyncSessionLocal = TestingSessionLocal
    
    # 创建所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # 清理 - 删除所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    # 恢复原始引擎
    database.engine = original_engine
    database.AsyncSessionLocal = original_sessionlocal


@pytest.fixture
async def db_session(setup_test_db) -> AsyncGenerator[AsyncSession, None]:
    """提供数据库会话"""
    async with TestingSessionLocal() as session:
        yield session


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """覆盖应用程序的数据库依赖"""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client(setup_test_db) -> AsyncGenerator[AsyncClient, None]:
    """创建测试客户端"""
    # 覆盖应用程序的数据库依赖
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    # 清理依赖覆盖
    app.dependency_overrides.clear()


# E2E测试的数据fixtures
@pytest.fixture
async def test_tenant_and_users(db_session: AsyncSession):
    """创建测试租户和用户数据"""
    from app.models.tenant import Tenant, TenantStatus, TenantPlan
    from app.models.user import User
    
    # 创建测试租户
    tenant = Tenant(
        id="5681d7bbbc4e42008a9e46ce04ed298d",
        name="测试企业",
        email="test@company.com",
        status=TenantStatus.ACTIVE,
        plan=TenantPlan.BASIC,
        api_key="test_api_key_12345678",
        extra_data={}
    )
    db_session.add(tenant)
    
    # 创建测试用户
    agent_user = User(
        id="webchat:test_agent_001",
        tenant_id=tenant.id,
        platform="webchat",
        user_id="test_agent_001",
        nickname="测试客服",
        extra_data={}
    )
    
    customer_user = User(
        id="webchat:test_customer_001",
        tenant_id=tenant.id,
        platform="webchat", 
        user_id="test_customer_001",
        nickname="测试用户",
        extra_data={}
    )
    
    db_session.add(agent_user)
    db_session.add(customer_user)
    await db_session.commit()
    
    return {
        "tenant": tenant,
        "agent_user": agent_user,
        "customer_user": customer_user
    }


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession):
    """
    创建测试租户
    """
    # TODO: 在实现Tenant模型后，这里创建测试租户
    # from app.models.tenant import Tenant
    # 
    # tenant = Tenant(
    #     name="Test Company",
    #     email="test@example.com",
    #     domain="test.example.com",
    #     is_active=True
    # )
    # db_session.add(tenant)
    # await db_session.commit()
    # await db_session.refresh(tenant)
    # return tenant
    
    # 临时返回模拟数据
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Test Company",
        "email": "test@example.com"
    }


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_tenant):
    """
    创建测试用户
    """
    # TODO: 在实现User模型后，这里创建测试用户
    # from app.models.user import User
    # 
    # user = User(
    #     email="testuser@example.com",
    #     hashed_password="hashed_password",
    #     tenant_id=test_tenant.id,
    #     is_active=True
    # )
    # db_session.add(user)
    # await db_session.commit()
    # await db_session.refresh(user)
    # return user
    
    # 临时返回模拟数据
    return {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "email": "testuser@example.com",
        "tenant_id": test_tenant["id"]
    }


@pytest_asyncio.fixture
async def auth_token(test_user):
    """
    生成测试用的JWT token
    """
    # TODO: 在实现JWT服务后，这里生成真实token
    # from app.core.security import create_access_token
    # 
    # token_data = {
    #     "sub": str(test_user.id),
    #     "tenant_id": str(test_user.tenant_id)
    # }
    # return create_access_token(data=token_data)
    
    # 临时返回模拟token
    return "mock_jwt_token"


@pytest_asyncio.fixture  
async def authenticated_client(client: AsyncClient, auth_token: str) -> AsyncClient:
    """
    创建已认证的测试客户端
    """
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return client


# 测试数据工厂函数
def create_test_session_data(tenant_id: str, user_id: str = "test_user"):
    """
    创建测试会话数据
    """
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "platform": "test_platform",
        "channel": "test_channel",
        "status": "active"
    }


def create_test_message_data(
    session_id: str, 
    tenant_id: str, 
    message_type: str = "text",
    content: str = "Test message"
):
    """
    创建测试消息数据
    """
    return {
        "session_id": session_id,
        "tenant_id": tenant_id,
        "content": content,
        "message_type": message_type,
        "sender_type": "user",
        "platform": "test_platform"
    } 