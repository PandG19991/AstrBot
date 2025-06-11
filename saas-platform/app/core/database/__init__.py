"""
数据库配置和连接管理

提供SQLAlchemy异步数据库引擎和会话管理。
"""

from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.utils.logging import get_logger

# 设置日志记录器
logger = get_logger(__name__)

# 创建异步数据库引擎
engine = create_async_engine(
    "sqlite+aiosqlite:///./test.db",  # 使用SQLite进行测试  ，正式环境使用PostgreSQL
    echo=settings.is_development,  # 开发环境显示SQL语句
    future=True
)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 定义元数据约定，用于自动命名约束
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# 创建基础模型类 - 修复metadata冲突
base_metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=base_metadata)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖函数
    
    这是一个异步生成器，用于FastAPI的依赖注入系统。
    会自动处理会话的创建、提交和关闭。
    
    Yields:
        AsyncSession: 数据库会话实例
    """
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("创建数据库会话")
            yield session
            logger.debug("数据库会话使用完毕")
        except Exception as e:
            logger.error(f"数据库会话异常: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug("数据库会话已关闭")


# 为了兼容性，保留get_db别名
get_db = get_db_session


async def init_db() -> None:
    """
    初始化数据库
    
    创建所有表格。在生产环境中，应该使用Alembic进行数据库迁移。
    """
    try:
        logger.info("开始初始化数据库")
        
        async with engine.begin() as conn:
            # 在生产环境中，这应该通过Alembic迁移来完成
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("数据库初始化完成")
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise


async def close_db() -> None:
    """
    关闭数据库连接
    
    应用关闭时调用，清理数据库连接。
    """
    try:
        logger.info("关闭数据库连接")
        await engine.dispose()
        logger.info("数据库连接已关闭")
        
    except Exception as e:
        logger.error(f"关闭数据库连接时发生异常: {str(e)}")
        raise
