# 📝 AstrBot SaaS 编码规范 - AI代码生成指南

## 🎯 编码原则

### 🔄 **核心原则**
1. **可读性优先**: 代码要易于理解和维护
2. **类型安全**: 使用完整的类型注解
3. **异步优先**: 所有I/O操作使用async/await
4. **多租户感知**: 所有数据操作都考虑租户隔离
5. **测试友好**: 代码设计便于单元测试

---

## 🐍 Python代码规范

### 📋 **命名约定**

```python
# ✅ 类名：大驼峰命名
class TenantService:
    pass

class MessageProcessor:
    pass

# ✅ 函数和变量名：下划线命名
async def create_tenant(tenant_data: TenantCreate) -> Tenant:
    session_id = generate_uuid()
    user_agent = request.headers.get("user-agent")

# ✅ 常量：全大写
DATABASE_URL = "postgresql://..."
JWT_SECRET_KEY = "your-secret-key"
TOKEN_EXPIRY_MINUTES = 30

# ✅ 枚举类：大驼峰 + 成员大写
class SessionStatus(Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    TRANSFERRED = "transferred"

# ✅ 事件处理函数：handle前缀
async def handle_message_received(message: IncomingMessage):
    pass

async def handle_session_closed(session: Session):
    pass
```

### 🎯 **类型注解规范**

```python
# ✅ 完整的类型注解
from typing import List, Optional, Dict, Union
from uuid import UUID
from datetime import datetime

# 函数参数和返回值
async def get_session_messages(
    db: AsyncSession,
    tenant_id: UUID,
    session_id: UUID,
    limit: int = 50,
    offset: int = 0
) -> List[Message]:
    pass

# 可选参数使用Optional
async def find_user(
    db: AsyncSession, 
    user_id: Optional[UUID] = None,
    email: Optional[str] = None
) -> Optional[User]:
    pass

# 复杂类型使用具体类型
UserRoleMap = Dict[UUID, List[str]]
MessageStats = Dict[str, Union[int, float, datetime]]

# 泛型使用
from typing import TypeVar, Generic

T = TypeVar('T')

class Repository(Generic[T]):
    async def create(self, entity: T) -> T:
        pass
```

### 🛡️ **异常处理模式**

```python
# ✅ 自定义异常继承体系
class AstrBotException(Exception):
    """Base exception for AstrBot SaaS"""
    pass

class ValidationError(AstrBotException):
    """数据验证错误"""
    pass

class TenantNotFoundError(AstrBotException):
    """租户不存在错误"""
    pass

class SessionNotFoundError(AstrBotException):
    """会话不存在错误"""
    pass

# ✅ Service层异常处理
async def get_tenant(self, db: AsyncSession, tenant_id: UUID) -> Tenant:
    try:
        result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise TenantNotFoundError(f"Tenant {tenant_id} not found")
        
        return tenant
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting tenant {tenant_id}: {e}")
        raise AstrBotException("Database operation failed")

# ✅ API层异常处理
@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    service: TenantService = Depends()
):
    try:
        # 验证访问权限
        if tenant_id != current_tenant.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        tenant = await service.get_tenant(tenant_id)
        return tenant
        
    except TenantNotFoundError:
        raise HTTPException(status_code=404, detail="Tenant not found")
    except AstrBotException as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 📚 **日志记录规范**

```python
import logging
import structlog

# ✅ 结构化日志配置
logger = structlog.get_logger(__name__)

# ✅ Service层日志记录
async def create_message(
    self, 
    db: AsyncSession,
    tenant_id: UUID,
    message_data: MessageCreate
) -> Message:
    logger.info(
        "Creating message",
        tenant_id=str(tenant_id),
        message_type=message_data.message_type,
        session_id=str(message_data.session_id)
    )
    
    try:
        message = Message(
            tenant_id=tenant_id,
            **message_data.dict()
        )
        db.add(message)
        await db.commit()
        
        logger.info(
            "Message created successfully",
            message_id=str(message.id),
            tenant_id=str(tenant_id)
        )
        
        return message
        
    except Exception as e:
        logger.error(
            "Failed to create message",
            tenant_id=str(tenant_id),
            error=str(e),
            exc_info=True
        )
        raise

# ✅ API层请求日志
@router.post("/messages")
async def create_message(
    message_data: MessageCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    request: Request = None
):
    logger.info(
        "API request received",
        endpoint="create_message",
        tenant_id=str(current_tenant.id),
        user_agent=request.headers.get("user-agent"),
        request_id=request.state.request_id
    )
```

---

## 🏗️ 架构设计模式

### 📦 **目录结构规范**

```
app/
├── api/                    # API路由层
│   ├── v1/                # API版本
│   │   ├── tenants.py     # 租户相关API
│   │   ├── sessions.py    # 会话相关API
│   │   └── messages.py    # 消息相关API
│   └── deps.py            # 依赖注入
├── core/                   # 核心配置
│   ├── config.py          # 应用配置
│   ├── security.py        # 安全相关
│   ├── database.py        # 数据库配置
│   └── exceptions.py      # 自定义异常
├── models/                 # SQLAlchemy模型
│   ├── __init__.py        # 模型导入
│   ├── tenant.py          # 租户模型
│   ├── user.py            # 用户模型
│   ├── session.py         # 会话模型
│   └── message.py         # 消息模型
├── schemas/                # Pydantic模式
│   ├── tenant.py          # 租户schema
│   ├── session.py         # 会话schema
│   └── message.py         # 消息schema
├── services/               # 业务逻辑层
│   ├── tenant_service.py  # 租户服务
│   ├── session_service.py # 会话服务
│   └── message_service.py # 消息服务
└── utils/                  # 工具函数
    ├── auth.py            # 认证工具
    ├── validators.py      # 验证器
    └── helpers.py         # 辅助函数
```

### 🔧 **Service层设计模式**

```python
# ✅ Service基类设计
class BaseService:
    """服务基类 - 提供通用功能"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def commit(self) -> None:
        """提交事务"""
        await self.db.commit()
    
    async def rollback(self) -> None:
        """回滚事务"""
        await self.db.rollback()

# ✅ 具体Service实现
class TenantService(BaseService):
    """租户管理服务"""
    
    async def create_tenant(self, tenant_data: TenantCreate) -> Tenant:
        """创建租户
        
        Args:
            tenant_data: 租户创建数据
            
        Returns:
            创建的租户对象
            
        Raises:
            ValidationError: 数据验证失败
            TenantExistsError: 租户已存在
        """
        # 验证租户邮箱唯一性
        existing = await self._find_by_email(tenant_data.email)
        if existing:
            raise TenantExistsError(f"Tenant with email {tenant_data.email} already exists")
        
        # 创建租户
        tenant = Tenant(**tenant_data.dict())
        self.db.add(tenant)
        await self.commit()
        
        logger.info("Tenant created", tenant_id=str(tenant.id))
        return tenant
    
    async def _find_by_email(self, email: str) -> Optional[Tenant]:
        """私有方法：按邮箱查找租户"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.email == email)
        )
        return result.scalar_one_or_none()
```

### 🎯 **API端点设计模式**

```python
# ✅ API路由设计
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])

@router.post(
    "/",
    response_model=TenantRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建租户",
    description="创建新的租户账户"
)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(get_current_admin_user),  # 只有管理员可创建
    service: TenantService = Depends(get_tenant_service)
) -> TenantRead:
    """
    创建租户API端点
    
    - **name**: 租户名称
    - **email**: 租户邮箱（唯一）
    - **domain**: 租户域名（可选）
    """
    try:
        tenant = await service.create_tenant(tenant_data)
        return TenantRead.from_orm(tenant)
        
    except TenantExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.get(
    "/{tenant_id}",
    response_model=TenantRead,
    summary="获取租户信息"
)
async def get_tenant(
    tenant_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    service: TenantService = Depends(get_tenant_service)
) -> TenantRead:
    """获取租户详细信息"""
    
    # 租户隔离检查
    if tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    tenant = await service.get_tenant(tenant_id)
    return TenantRead.from_orm(tenant)
```

### 📊 **数据模型设计模式**

```python
# ✅ SQLAlchemy模型设计
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

Base = declarative_base()

class TimestampMixin:
    """时间戳混合类"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Tenant(Base, TimestampMixin):
    """租户模型"""
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, comment="租户名称")
    email = Column(String(255), unique=True, nullable=False, comment="租户邮箱")
    domain = Column(String(255), comment="租户域名")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    
    # 关联关系
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="tenant")
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}')>"

class User(Base, TimestampMixin):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('tenants.id'), nullable=False)  # 🚨 多租户关联
    username = Column(String(50), nullable=False, comment="用户名")
    email = Column(String(255), nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="加密密码")
    is_active = Column(Boolean, default=True, nullable=False)
    
    # 关联关系
    tenant = relationship("Tenant", back_populates="users")
    
    # 唯一约束：租户内用户名唯一
    __table_args__ = (
        UniqueConstraint('tenant_id', 'username', name='uk_tenant_username'),
        UniqueConstraint('tenant_id', 'email', name='uk_tenant_email'),
    )
```

---

## 🧪 测试代码规范

### 📋 **测试命名和结构**

```python
# ✅ 测试文件命名
# tests/unit/test_tenant_service.py
# tests/integration/test_tenant_api.py
# tests/e2e/test_tenant_workflow.py

# ✅ 测试类和方法命名
class TestTenantService:
    """租户服务测试类"""
    
    async def test_create_tenant_success(self):
        """测试成功创建租户"""
        pass
    
    async def test_create_tenant_duplicate_email_fails(self):
        """测试重复邮箱创建租户失败"""
        pass
    
    async def test_get_tenant_not_found_raises_exception(self):
        """测试获取不存在租户抛出异常"""
        pass

# ✅ 测试fixture设计
@pytest.fixture
async def db_session():
    """数据库会话fixture"""
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def sample_tenant(db_session):
    """样本租户fixture"""
    tenant_data = TenantCreate(
        name="Test Tenant",
        email="test@example.com"
    )
    service = TenantService(db_session)
    return await service.create_tenant(tenant_data)

# ✅ 测试用例结构
async def test_create_message_with_valid_data(
    db_session,
    sample_tenant,
    sample_session
):
    """测试使用有效数据创建消息"""
    # Arrange
    message_data = MessageCreate(
        session_id=sample_session.id,
        content="Hello, world!",
        message_type="text",
        sender_type="customer"
    )
    service = MessageService(db_session)
    
    # Act
    message = await service.create_message(
        tenant_id=sample_tenant.id,
        message_data=message_data
    )
    
    # Assert
    assert message.id is not None
    assert message.tenant_id == sample_tenant.id
    assert message.content == "Hello, world!"
    assert message.message_type == "text"
```

---

## 🎨 代码风格工具配置

### ⚙️ **工具配置文件**

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.mypy_cache
  | \.pytest_cache
  | \.venv
  | build
  | dist
)/
'''

[tool.ruff]
line-length = 88
target-version = "py311"
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "N",  # pep8-naming
    "B",  # flake8-bugbear
    "A",  # flake8-builtins
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true

# 数据库模型类型检查
plugins = ["sqlalchemy.ext.mypy.plugin"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=app",
    "--cov-report=term-missing:skip-covered",
    "--cov-report=html",
    "--cov-fail-under=80"
]
```

---

## 💡 AI代码生成提示

### 📝 **代码生成检查清单**

每次生成代码时，AI应自动检查：

- [ ] **类型注解**: 所有函数参数和返回值都有类型注解
- [ ] **多租户隔离**: 数据操作包含tenant_id过滤
- [ ] **异常处理**: Service方法包含适当的异常处理
- [ ] **日志记录**: 关键操作包含结构化日志
- [ ] **文档字符串**: 公共方法有docstring说明
- [ ] **测试用例**: 同时生成对应的测试代码

### 🎯 **代码生成模板**

```python
# AI生成Service方法模板
async def {method_name}(
    self,
    db: AsyncSession,
    tenant_id: UUID,  # 🚨 必须参数
    {other_params}
) -> {return_type}:
    """
    {method_description}
    
    Args:
        db: 数据库会话
        tenant_id: 租户ID
        {param_descriptions}
        
    Returns:
        {return_description}
        
    Raises:
        {exception_descriptions}
    """
    logger.info(
        "{log_message}",
        tenant_id=str(tenant_id),
        {log_fields}
    )
    
    try:
        # 业务逻辑实现
        {business_logic}
        
        await self.commit()
        
        logger.info(
            "{success_message}",
            tenant_id=str(tenant_id),
            {success_fields}
        )
        
        return {result}
        
    except {SpecificException} as e:
        logger.error(
            "{error_message}",
            tenant_id=str(tenant_id),
            error=str(e)
        )
        raise
```

---

**文档版本**: v1.0  
**更新时间**: 2024年  
**适用性**: 🤖 AI代码生成标准指南 