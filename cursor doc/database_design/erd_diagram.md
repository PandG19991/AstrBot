# 📊 实体关系图 (ERD)

## 📑 目录
- [1. 整体ERD图](#1-整体erd图)
- [2. 核心业务域关系](#2-核心业务域关系)
- [3. 表关系详解](#3-表关系详解)
- [4. 约束与索引说明](#4-约束与索引说明)

---

## 1. 整体ERD图

### 🏗️ 主要业务域关系图

```mermaid
erDiagram
    TENANTS ||--o{ TENANT_CONFIGS : "配置"
    TENANTS ||--o{ USERS : "管理"
    TENANTS ||--o{ SESSIONS : "拥有"
    TENANTS ||--o{ BLACKLIST : "维护"
    TENANTS ||--o{ LLM_CONFIGS : "配置"
    TENANTS ||--o{ WEBHOOK_CONFIGS : "设置"
    
    USERS ||--o{ SESSIONS : "参与"
    USERS ||--o{ MESSAGES : "发送"
    
    SESSIONS ||--o{ MESSAGES : "包含"
    SESSIONS ||--o{ SESSION_CONTEXTS : "维护"
    
    LLM_CONFIGS ||--o{ LLM_REQUESTS : "使用"
    LLM_CONFIGS ||--o{ TOKEN_USAGE : "产生"
    
    WEBHOOK_CONFIGS ||--o{ WEBHOOK_LOGS : "记录"
    
    MESSAGES ||--o{ MESSAGE_EMBEDDINGS : "向量化"
    
    TENANTS {
        uuid id PK
        varchar name
        varchar email
        enum status
        varchar plan
        timestamp created_at
        timestamp updated_at
    }
    
    TENANT_CONFIGS {
        uuid id PK
        uuid tenant_id FK
        json config_data
        timestamp created_at
        timestamp updated_at
    }
    
    USERS {
        varchar id PK "platform:user_id"
        uuid tenant_id FK
        varchar platform
        varchar user_id
        varchar nickname
        json metadata
        timestamp created_at
        timestamp updated_at
    }
    
    SESSIONS {
        varchar id PK
        uuid tenant_id FK
        varchar user_id FK
        varchar platform
        enum status
        varchar assigned_staff
        timestamp created_at
        timestamp updated_at
        timestamp last_message_at
    }
    
    MESSAGES {
        bigint id PK
        uuid tenant_id FK
        varchar session_id FK
        varchar content
        enum type
        enum direction
        varchar sender_id
        json metadata
        timestamp created_at
    }
    
    SESSION_CONTEXTS {
        uuid id PK
        uuid tenant_id FK
        varchar session_id FK
        text context_summary
        int message_count
        timestamp last_updated
    }
    
    BLACKLIST {
        uuid id PK
        uuid tenant_id FK
        varchar platform
        varchar user_id
        varchar reason
        varchar created_by
        timestamp created_at
    }
    
    LLM_CONFIGS {
        uuid id PK
        uuid tenant_id FK
        varchar provider
        varchar model
        json config_params
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }
    
    LLM_REQUESTS {
        uuid id PK
        uuid tenant_id FK
        uuid llm_config_id FK
        varchar session_id
        int prompt_tokens
        int completion_tokens
        decimal cost
        timestamp created_at
    }
    
    TOKEN_USAGE {
        uuid id PK
        uuid tenant_id FK
        uuid llm_config_id FK
        date usage_date
        int total_prompt_tokens
        int total_completion_tokens
        decimal total_cost
    }
    
    WEBHOOK_CONFIGS {
        uuid id PK
        uuid tenant_id FK
        varchar platform
        varchar webhook_url
        varchar secret_token
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }
    
    WEBHOOK_LOGS {
        uuid id PK
        uuid tenant_id FK
        uuid webhook_config_id FK
        varchar event_type
        json payload
        int response_status
        text response_body
        timestamp created_at
    }
    
    MESSAGE_EMBEDDINGS {
        uuid id PK
        uuid tenant_id FK
        bigint message_id FK
        vector embedding
        timestamp created_at
    }
```

---

## 2. 核心业务域关系

### 🏢 租户管理域

```mermaid
erDiagram
    TENANTS ||--|| TENANT_CONFIGS : "一对一配置"
    TENANTS ||--o{ BILLING_RECORDS : "计费记录"
    TENANTS ||--o{ USAGE_QUOTAS : "使用配额"
    
    TENANTS {
        uuid id PK
        varchar name "租户名称"
        varchar email "管理员邮箱"
        enum status "active|suspended|pending"
        varchar plan "basic|standard|premium"
        json metadata "扩展信息"
        timestamp created_at
        timestamp updated_at
    }
    
    TENANT_CONFIGS {
        uuid id PK
        uuid tenant_id FK
        int max_sessions "最大会话数"
        int max_monthly_tokens "月度Token限制"
        json ui_customization "界面定制"
        json feature_flags "功能开关"
        timestamp created_at
        timestamp updated_at
    }
    
    BILLING_RECORDS {
        uuid id PK
        uuid tenant_id FK
        varchar billing_cycle
        int token_usage
        decimal amount
        enum status "pending|paid|overdue"
        timestamp billing_date
        timestamp paid_at
    }
    
    USAGE_QUOTAS {
        uuid id PK
        uuid tenant_id FK
        varchar quota_type "tokens|sessions|storage"
        int quota_limit
        int quota_used
        date reset_date
        timestamp created_at
        timestamp updated_at
    }
```

### 💬 消息会话域

```mermaid
erDiagram
    SESSIONS ||--o{ MESSAGES : "包含多条消息"
    SESSIONS ||--|| SESSION_CONTEXTS : "维护上下文"
    SESSIONS ||--o{ SESSION_TRANSFERS : "转接记录"
    
    MESSAGES ||--o{ MESSAGE_ATTACHMENTS : "包含附件"
    MESSAGES ||--o{ MESSAGE_REACTIONS : "用户反馈"
    
    SESSIONS {
        varchar id PK "session_id"
        uuid tenant_id FK
        varchar user_id "用户标识"
        varchar platform "来源平台"
        enum status "active|closed|transferred"
        varchar assigned_staff "分配客服"
        json metadata "扩展数据"
        timestamp created_at
        timestamp updated_at
        timestamp last_message_at
    }
    
    MESSAGES {
        bigint id PK
        uuid tenant_id FK
        varchar session_id FK
        text content "消息内容"
        enum type "text|image|voice|file"
        enum direction "inbound|outbound"
        varchar sender_id "发送者ID"
        varchar reply_to_id "回复消息ID"
        json metadata "消息元数据"
        timestamp created_at
    }
    
    SESSION_CONTEXTS {
        uuid id PK
        uuid tenant_id FK
        varchar session_id FK
        text context_summary "上下文摘要"
        json key_entities "关键实体"
        int message_count "消息数量"
        float sentiment_score "情感分数"
        timestamp last_updated
    }
    
    SESSION_TRANSFERS {
        uuid id PK
        uuid tenant_id FK
        varchar session_id FK
        varchar from_staff "转出客服"
        varchar to_staff "转入客服"
        text transfer_reason "转接原因"
        timestamp transferred_at
    }
    
    MESSAGE_ATTACHMENTS {
        uuid id PK
        uuid tenant_id FK
        bigint message_id FK
        varchar filename "文件名"
        varchar file_type "文件类型"
        int file_size "文件大小"
        varchar storage_path "存储路径"
        timestamp created_at
    }
    
    MESSAGE_REACTIONS {
        uuid id PK
        uuid tenant_id FK
        bigint message_id FK
        varchar user_id "反馈用户"
        enum reaction_type "like|dislike|helpful"
        text feedback_text "反馈文本"
        timestamp created_at
    }
```

### 🤖 LLM集成域

```mermaid
erDiagram
    LLM_CONFIGS ||--o{ LLM_REQUESTS : "产生请求"
    LLM_CONFIGS ||--o{ LLM_MODELS : "使用模型"
    
    LLM_REQUESTS ||--|| TOKEN_USAGE : "记录用量"
    LLM_REQUESTS ||--o{ LLM_RESPONSES : "生成响应"
    
    LLM_CONFIGS {
        uuid id PK
        uuid tenant_id FK
        varchar provider "openai|claude|qianwen"
        varchar model_name "模型名称"
        json config_params "配置参数"
        boolean is_active "是否启用"
        int priority "优先级"
        timestamp created_at
        timestamp updated_at
    }
    
    LLM_MODELS {
        varchar id PK "model_id"
        varchar provider "提供商"
        varchar model_name "模型名称"
        decimal input_price "输入价格/1K tokens"
        decimal output_price "输出价格/1K tokens"
        int max_tokens "最大Token数"
        json capabilities "能力描述"
        boolean is_available "是否可用"
    }
    
    LLM_REQUESTS {
        uuid id PK
        uuid tenant_id FK
        uuid llm_config_id FK
        varchar session_id FK
        text prompt "提示词"
        json request_params "请求参数"
        int prompt_tokens "输入Token数"
        int completion_tokens "输出Token数"
        decimal cost "费用"
        float response_time "响应时间(秒)"
        timestamp created_at
    }
    
    LLM_RESPONSES {
        uuid id PK
        uuid llm_request_id FK
        text content "响应内容"
        json metadata "响应元数据"
        enum status "success|error|timeout"
        text error_message "错误信息"
        timestamp created_at
    }
    
    TOKEN_USAGE {
        uuid id PK
        uuid tenant_id FK
        uuid llm_config_id FK
        date usage_date "使用日期"
        int daily_prompt_tokens "日输入Token"
        int daily_completion_tokens "日输出Token"
        decimal daily_cost "日费用"
        int monthly_prompt_tokens "月输入Token"
        int monthly_completion_tokens "月输出Token"
        decimal monthly_cost "月费用"
    }
```

---

## 3. 表关系详解

### 🔗 主键与外键约束

#### 1. 租户隔离约束
```sql
-- 所有业务表都包含 tenant_id 外键
ALTER TABLE sessions 
ADD CONSTRAINT fk_sessions_tenant 
FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

-- 复合外键确保跨表查询的租户一致性
ALTER TABLE messages 
ADD CONSTRAINT fk_messages_session_tenant 
FOREIGN KEY (tenant_id, session_id) REFERENCES sessions(tenant_id, id);
```

#### 2. 级联删除策略
```sql
-- 租户删除时级联删除所有相关数据
CREATE TABLE sessions (
    id VARCHAR(255) PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    -- 其他字段...
);

-- 会话删除时级联删除消息
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    -- 其他字段...
);
```

#### 3. 数据完整性约束
```sql
-- 枚举类型约束
CREATE TYPE tenant_status AS ENUM ('active', 'suspended', 'pending');
CREATE TYPE session_status AS ENUM ('active', 'closed', 'transferred');
CREATE TYPE message_type AS ENUM ('text', 'image', 'voice', 'file', 'system');

-- 检查约束
ALTER TABLE messages 
ADD CONSTRAINT chk_content_not_empty 
CHECK (LENGTH(content) > 0);

ALTER TABLE llm_requests 
ADD CONSTRAINT chk_tokens_positive 
CHECK (prompt_tokens >= 0 AND completion_tokens >= 0);
```

### 📊 索引策略说明

#### 1. 高频查询索引
```sql
-- 租户+时间范围查询
CREATE INDEX idx_messages_tenant_time 
ON messages (tenant_id, created_at DESC);

-- 会话消息查询
CREATE INDEX idx_messages_session_time 
ON messages (session_id, created_at DESC);

-- 用户会话查询
CREATE INDEX idx_sessions_user_status 
ON sessions (tenant_id, user_id, status);
```

#### 2. 复合索引设计
```sql
-- 支持多维度筛选的复合索引
CREATE INDEX idx_sessions_multi_filter 
ON sessions (tenant_id, platform, status, created_at DESC);

-- 覆盖索引减少回表查询
CREATE INDEX idx_messages_summary 
ON messages (session_id, created_at DESC) 
INCLUDE (content, type, sender_id);
```

#### 3. 部分索引优化
```sql
-- 只为活跃会话创建索引
CREATE INDEX idx_active_sessions 
ON sessions (tenant_id, last_message_at DESC) 
WHERE status = 'active';

-- 只为近期消息创建全文索引
CREATE INDEX idx_recent_message_content 
ON messages USING gin(to_tsvector('english', content))
WHERE created_at > CURRENT_DATE - INTERVAL '90 days';
```

---

## 4. 约束与索引说明

### ⚡ 性能优化索引

| 索引名称 | 表名 | 字段 | 用途 | 估算查询性能提升 |
|----------|------|------|------|------------------|
| `idx_messages_tenant_session_time` | messages | (tenant_id, session_id, created_at) | 会话消息查询 | 100x |
| `idx_sessions_tenant_user` | sessions | (tenant_id, user_id) | 用户会话查询 | 50x |
| `idx_llm_requests_tenant_date` | llm_requests | (tenant_id, created_at) | Token使用统计 | 20x |
| `idx_blacklist_tenant_platform_user` | blacklist | (tenant_id, platform, user_id) | 黑名单检查 | 200x |

### 🔒 数据完整性约束

#### 1. 业务逻辑约束
```sql
-- 确保会话状态转换的合理性
CREATE OR REPLACE FUNCTION validate_session_status_transition()
RETURNS TRIGGER AS $$
BEGIN
    -- 只能从 active 转为 closed 或 transferred
    IF OLD.status = 'active' AND NEW.status NOT IN ('closed', 'transferred') THEN
        RAISE EXCEPTION '无效的会话状态转换: % -> %', OLD.status, NEW.status;
    END IF;
    
    -- closed 状态不能再转换
    IF OLD.status = 'closed' AND NEW.status != 'closed' THEN
        RAISE EXCEPTION '已关闭的会话不能重新激活';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_session_status_validation
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION validate_session_status_transition();
```

#### 2. 数据一致性约束
```sql
-- 确保消息的 tenant_id 与会话一致
CREATE OR REPLACE FUNCTION validate_message_tenant_consistency()
RETURNS TRIGGER AS $$
DECLARE
    session_tenant_id UUID;
BEGIN
    SELECT tenant_id INTO session_tenant_id 
    FROM sessions 
    WHERE id = NEW.session_id;
    
    IF session_tenant_id != NEW.tenant_id THEN
        RAISE EXCEPTION '消息的租户ID与会话不一致';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_message_tenant_consistency
    BEFORE INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION validate_message_tenant_consistency();
```

### 📈 分区表设计

#### 1. 消息表按时间分区
```sql
-- 主表定义
CREATE TABLE messages (
    id BIGSERIAL,
    tenant_id UUID NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    -- 其他字段...
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 自动创建月度分区的函数
CREATE OR REPLACE FUNCTION create_monthly_message_partition(target_date DATE)
RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    start_date := DATE_TRUNC('month', target_date);
    end_date := start_date + INTERVAL '1 month';
    partition_name := 'messages_' || TO_CHAR(start_date, 'YYYY_MM');
    
    EXECUTE format(
        'CREATE TABLE %I PARTITION OF messages
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
    
    -- 为分区表创建索引
    EXECUTE format(
        'CREATE INDEX %I ON %I (tenant_id, session_id, created_at DESC)',
        'idx_' || partition_name || '_tenant_session_time',
        partition_name
    );
END;
$$ LANGUAGE plpgsql;
```

#### 2. 自动分区维护
```sql
-- 定期创建新分区的任务
CREATE OR REPLACE FUNCTION maintain_message_partitions()
RETURNS VOID AS $$
DECLARE
    target_month DATE;
BEGIN
    -- 为未来3个月创建分区
    FOR i IN 0..2 LOOP
        target_month := DATE_TRUNC('month', CURRENT_DATE + (i || ' months')::INTERVAL);
        
        -- 检查分区是否已存在
        IF NOT EXISTS (
            SELECT 1 FROM pg_tables 
            WHERE tablename = 'messages_' || TO_CHAR(target_month, 'YYYY_MM')
        ) THEN
            PERFORM create_monthly_message_partition(target_month);
        END IF;
    END LOOP;
    
    -- 删除6个月前的旧分区（根据数据保留策略）
    -- 这里仅作示例，实际应根据业务需求调整
END;
$$ LANGUAGE plpgsql;

-- 创建定时任务（需要 pg_cron 扩展）
SELECT cron.schedule('maintain-partitions', '0 0 1 * *', 'SELECT maintain_message_partitions();');
```

---

**ERD文档版本**: v1.0  
**最后更新**: 2024年  
**维护责任人**: 数据库设计团队 