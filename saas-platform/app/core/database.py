"""
数据库连接配置模块
使用SQLAlchemy 2.0异步模式，支持PostgreSQL
"""
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase

from app.core.config.settings import get_settings

# 配置日志
logger = logging.getLogger(__name__)

# 获取应用设置
settings = get_settings()


class Base(DeclarativeBase):
    """
    SQLAlchemy模型基类
    使用新的declarative_base语法
    """
    pass


# 创建异步数据库引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # 开发模式下显示SQL语句
    pool_pre_ping=True,   # 连接前ping检查
    pool_recycle=300,     # 连接回收时间（秒）
    pool_size=20,         # 连接池大小
    max_overflow=30,      # 最大溢出连接数
    future=True,          # 使用SQLAlchemy 2.0风格
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 提交后不过期对象
    autoflush=True,          # 自动刷新
    autocommit=False,        # 手动提交事务
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖注入函数
    用于FastAPI的Depends()
    
    Returns:
        AsyncSession: 数据库异步会话
        
    Example:
        @app.get("/items/")
        async def read_items(db: AsyncSession = Depends(get_db)):
            # 使用db进行数据库操作
    """
    async with AsyncSessionLocal() as session:
        try:
            logger.debug("创建数据库会话")
            yield session
        except Exception as e:
            logger.error(f"数据库会话错误: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug("关闭数据库会话")


async def init_db() -> None:
    """
    初始化数据库
    创建所有表（仅在开发环境使用）
    
    Note:
        生产环境应使用Alembic进行数据库迁移
    """
    try:
        logger.info("开始初始化数据库")
        async with engine.begin() as conn:
            # 导入所有模型以确保它们被注册
            # TODO: 在创建模型后取消注释
            # from app.models import tenant, user, session, message
            
            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库表创建完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise


async def close_db() -> None:
    """
    关闭数据库连接池
    用于应用关闭时清理资源
    """
    try:
        logger.info("关闭数据库连接池")
        await engine.dispose()
        logger.info("数据库连接池已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接池失败: {str(e)}")
        raise


async def check_db_connection() -> bool:
    """
    检查数据库连接状态
    
    Returns:
        bool: 连接正常返回True，否则返回False
    """
    try:
        async with AsyncSessionLocal() as session:
            # 执行简单查询测试连接
            result = await session.execute("SELECT 1")
            result.scalar()
            logger.info("数据库连接正常")
            return True
    except Exception as e:
        logger.error(f"数据库连接检查失败: {str(e)}")
        return False


# 数据库健康检查函数
async def health_check() -> dict:
    """
    数据库健康检查
    
    Returns:
        dict: 包含连接状态和延迟信息
    """
    import time
    
    start_time = time.time()
    is_healthy = await check_db_connection()
    end_time = time.time()
    
    return {
        "database": {
            "status": "healthy" if is_healthy else "unhealthy",
            "response_time_ms": round((end_time - start_time) * 1000, 2),
            "url": settings.DATABASE_URL.replace(
                settings.DB_PASSWORD, "***"
            ) if settings.DB_PASSWORD else settings.DATABASE_URL
        }
    } 