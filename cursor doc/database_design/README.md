# 🗄️ 数据库设计文档

## 📑 目录
- [1. 设计概述](#1-设计概述)
- [2. 文档结构](#2-文档结构)
- [3. 设计原则](#3-设计原则)
- [4. 使用指南](#4-使用指南)

---

## 1. 设计概述

本目录包含AstrBot SaaS平台的完整数据库设计规范，涵盖逻辑设计、物理设计、性能优化和数据安全等方面。设计遵循第三范式，确保数据一致性和系统可扩展性。

### 🎯 设计目标
- **多租户隔离**: 确保租户间数据完全隔离
- **高可用性**: 支持读写分离和数据备份恢复
- **性能优化**: 合理的索引设计和查询优化
- **数据安全**: 敏感数据加密和访问控制
- **扩展性**: 支持水平扩展和分库分表

### 📊 技术选型
- **主数据库**: PostgreSQL 14+
- **缓存数据库**: Redis 7+
- **向量数据库**: Milvus 2.3+ (用于LLM上下文相似性搜索)
- **连接池**: PgBouncer
- **ORM框架**: SQLAlchemy (Python) / Prisma (Node.js)

---

## 2. 文档结构

### 📋 文件组织
```
database_design/
├── README.md                          # 本文档
├── erd_diagram.md                     # 实体关系图
├── table_schemas/                     # 表结构定义
│   ├── core_tables.sql                # 核心业务表
│   ├── tenant_tables.sql              # 租户相关表
│   ├── message_tables.sql             # 消息相关表
│   ├── config_tables.sql              # 配置相关表
│   ├── analytics_tables.sql           # 统计分析表
│   └── system_tables.sql              # 系统管理表
├── indexes/                           # 索引设计
│   ├── performance_indexes.sql        # 性能索引
│   ├── unique_indexes.sql             # 唯一性索引
│   └── composite_indexes.sql          # 复合索引
├── migrations/                        # 数据库迁移
│   ├── 001_initial_schema.sql         # 初始化架构
│   ├── 002_add_tenant_isolation.sql   # 租户隔离
│   └── 003_performance_optimization.sql # 性能优化
├── stored_procedures/                  # 存储过程
│   ├── tenant_management.sql          # 租户管理
│   ├── message_processing.sql         # 消息处理
│   └── analytics_computation.sql      # 统计计算
├── views/                             # 视图定义
│   ├── tenant_dashboard_view.sql      # 租户仪表盘视图
│   ├── message_analytics_view.sql     # 消息分析视图
│   └── system_monitoring_view.sql     # 系统监控视图
└── data_dictionary.md                 # 数据字典
```

### 🔧 表分类说明

| 表类别 | 文件 | 主要功能 | 记录估算 |
|--------|------|----------|----------|
| **核心业务表** | core_tables.sql | 租户、用户、会话管理 | 百万级 |
| **租户相关表** | tenant_tables.sql | 租户配置、权限、计费 | 万级 |
| **消息相关表** | message_tables.sql | 消息存储、上下文管理 | 千万级 |
| **配置相关表** | config_tables.sql | 系统配置、LLM配置 | 千级 |
| **统计分析表** | analytics_tables.sql | 使用统计、性能指标 | 百万级 |
| **系统管理表** | system_tables.sql | 审计日志、系统监控 | 百万级 |

---

## 3. 设计原则

### 🏗️ 架构原则

#### 1. 租户隔离策略
```sql
-- 方案一：共享数据库，独立Schema
CREATE SCHEMA tenant_12345;
CREATE TABLE tenant_12345.sessions (...);

-- 方案二：共享数据库，共享表，行级隔离(RLS)
CREATE POLICY tenant_isolation ON sessions
FOR ALL TO application_role
USING (tenant_id = current_setting('app.current_tenant_id'));
```

#### 2. 数据分区策略
```sql
-- 按时间分区存储消息表
CREATE TABLE messages (
    id BIGSERIAL,
    tenant_id UUID NOT NULL,
    session_id VARCHAR(255),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    -- 其他字段...
) PARTITION BY RANGE (created_at);

-- 创建月度分区
CREATE TABLE messages_2024_01 PARTITION OF messages
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

#### 3. 索引优化策略
```sql
-- 复合索引设计
CREATE INDEX idx_messages_tenant_session_time 
ON messages (tenant_id, session_id, created_at DESC);

-- 部分索引（减少索引大小）
CREATE INDEX idx_active_sessions 
ON sessions (tenant_id, user_id) 
WHERE status = 'active';

-- 覆盖索引（减少回表查询）
CREATE INDEX idx_session_summary 
ON sessions (tenant_id, status) 
INCLUDE (user_id, created_at, last_message_at);
```

### 📊 性能设计原则

#### 1. 查询优化
- **读写分离**: 读操作使用从库，写操作使用主库
- **查询缓存**: 热点数据使用Redis缓存
- **分页优化**: 使用cursor-based分页替代offset-based

#### 2. 存储优化
- **数据压缩**: 历史消息使用压缩存储
- **冷热分离**: 近期数据在SSD，历史数据在HDD
- **归档策略**: 定期归档和清理过期数据

### 🔒 安全设计原则

#### 1. 数据加密
```sql
-- 敏感字段加密存储
CREATE TABLE tenant_configs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    llm_api_key BYTEA, -- 使用 pgcrypto 加密
    webhook_secret BYTEA,
    -- 其他字段...
);

-- 加密函数示例
INSERT INTO tenant_configs (llm_api_key) 
VALUES (pgp_sym_encrypt('actual_api_key', 'encryption_key'));
```

#### 2. 访问控制
```sql
-- 创建应用角色
CREATE ROLE saas_app_role;
CREATE ROLE saas_admin_role;

-- 权限分配
GRANT SELECT, INSERT, UPDATE ON sessions TO saas_app_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO saas_admin_role;
```

---

## 4. 使用指南

### 🚀 快速开始

#### 1. 初始化数据库
```bash
# 创建数据库
createdb astrbot_saas

# 执行初始化脚本
psql -d astrbot_saas -f migrations/001_initial_schema.sql

# 创建索引
psql -d astrbot_saas -f indexes/performance_indexes.sql
```

#### 2. 开发环境设置
```python
# Python SQLAlchemy 配置示例
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://user:password@localhost/astrbot_saas"
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    echo=True  # 开发环境开启SQL日志
)

SessionLocal = sessionmaker(bind=engine)
```

#### 3. 租户隔离实现
```python
# 租户上下文管理器
from contextvars import ContextVar

current_tenant_id: ContextVar[str] = ContextVar('current_tenant_id')

def set_tenant_context(tenant_id: str):
    current_tenant_id.set(tenant_id)

# 在每个请求中设置租户上下文
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    tenant_id = extract_tenant_from_jwt(request.headers.get("authorization"))
    set_tenant_context(tenant_id)
    response = await call_next(request)
    return response
```

### 📝 开发最佳实践

#### 1. 数据库连接管理
```python
# 使用连接池和自动重连
class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(
            DATABASE_URL,
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True
        )
    
    def get_session(self):
        return SessionLocal()
    
    def execute_with_retry(self, query, max_retries=3):
        for attempt in range(max_retries):
            try:
                with self.get_session() as session:
                    return session.execute(query)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.1 * (2 ** attempt))  # 指数退避
```

#### 2. 查询优化示例
```python
# 使用预编译语句
class MessageRepository:
    def get_recent_messages(self, session_id: str, limit: int = 50):
        query = text("""
            SELECT id, content, sender_id, created_at 
            FROM messages 
            WHERE session_id = :session_id 
              AND tenant_id = :tenant_id
            ORDER BY created_at DESC 
            LIMIT :limit
        """)
        
        return session.execute(
            query, 
            {
                'session_id': session_id,
                'tenant_id': current_tenant_id.get(),
                'limit': limit
            }
        ).fetchall()
```

### 🔍 监控与维护

#### 1. 性能监控
```sql
-- 查询性能统计
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    stddev_time
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;

-- 索引使用统计
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

#### 2. 自动化维护脚本
```bash
#!/bin/bash
# 定期维护脚本

# 更新表统计信息
psql -d astrbot_saas -c "ANALYZE;"

# 重建索引（必要时）
psql -d astrbot_saas -c "REINDEX INDEX CONCURRENTLY idx_messages_tenant_session_time;"

# 清理过期数据
psql -d astrbot_saas -c "DELETE FROM messages WHERE created_at < NOW() - INTERVAL '1 year';"

# 压缩表空间
psql -d astrbot_saas -c "VACUUM (ANALYZE, VERBOSE);"
```

---

**数据库设计文档版本**: v1.0  
**最后更新**: 2024年  
**维护责任人**: 数据库团队 