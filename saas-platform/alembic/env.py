"""
Alembic环境配置
支持异步SQLAlchemy和多租户架构
"""
import asyncio
import logging
from logging.config import fileConfig
from pathlib import Path
import sys

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 添加app模块到路径
sys.path.append(str(Path(__file__).resolve().parents[1]))

# 导入应用模块
from app.core.config.settings import get_settings
from app.core.database import Base

# 获取应用设置
settings = get_settings()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置数据库URL（从应用配置读取）
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 包含模式前缀以支持多租户
        include_schemas=True,
        # 渲染表注释
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def render_item(type_, obj, autogen_context):
    """Apply custom rendering logic to migration items."""
    if type_ == "table" and hasattr(obj, "comment"):
        return f"# Table: {obj.name} - {obj.comment}\n"
    
    # Fall back to the default rendering.
    return False


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection, 
        target_metadata=target_metadata,
        # 包含模式前缀以支持多租户
        include_schemas=True,
        # 渲染表注释
        render_item=render_item,
        # 比较类型以检测字段类型变更
        compare_type=True,
        # 比较服务器默认值
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 创建异步引擎配置
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        configuration = {}

    configuration.setdefault("sqlalchemy.url", settings.DATABASE_URL)
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # 异步引擎配置
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 运行异步迁移
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
