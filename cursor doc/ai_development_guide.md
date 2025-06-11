# 🤖 AI协同开发指南

## 📋 项目核心信息

### 🎯 项目目标
**AstrBot SaaS改造项目**: 将单体AstrBot改造为多租户SaaS平台，支持多个企业用户独立使用智能客服服务。

### 🏗️ 核心架构模式
- **多租户架构**: 租户级数据隔离，共享应用实例
- **微服务设计**: SaaS平台 + AstrBot实例 双向通信
- **异步优先**: FastAPI + SQLAlchemy 2.0 + PostgreSQL
- **AI驱动**: LLM编排服务，支持多种AI模型

---

## 📚 文档体系地图

### 🎯 **核心设计文档** (开发必读)

| 文档名称 | 文件路径 | 用途 | AI开发阶段 |
|---|----|---|---|
| **项目概述** | `@cursor doc/README.md` | 项目背景、目标、核心价值 | 🔄 **贯穿全程** |
| **系统架构说明** | `@cursor doc/架构说明.md` | 整体架构、组件关系、技术选型 | 🔄 **贯穿全程** |
| **API契约设计** | `@cursor doc/api_contracts/README.md` | 完整API规范和数据模型 | 🏗️ **M1-M8 API开发** |
| **数据库设计** | `@cursor doc/database_design/README.md` | 数据模型、ERD图、索引策略 | 🏗️ **M1-M3 数据层** |
| **算法核心设计** | `@cursor doc/algorithms/README.md` | 会话分配、上下文管理算法 | 🧠 **M4 智能化阶段** |
| **后端开发计划** | `@cursor doc/后端开发计划.md` | 详细开发路线图和任务拆分 | 🔄 **贯穿全程** |

### 📊 **详细规范文档** (分阶段参考)

| 文档类型 | 文件路径 | 主要内容 | 适用里程碑 |
|---|----|----|---|
| **需求规格** | `@cursor doc/需求规格说明书.md` | 功能需求、非功能需求 | 🎯 **M0-M1 基础阶段** |
| **功能说明** | `@cursor doc/功能说明.md` | 业务功能详细描述 | 💼 **M2-M5 业务功能** |
| **技术栈指南** | `@cursor doc/技术栈.md` | 技术选型、版本要求 | ⚙️ **M0 环境搭建** |
| **开发规范** | `@cursor doc/开发规范.md` | 编码标准、API设计原则 | 🔄 **贯穿全程** |
| **测试用例** | `@cursor doc/测试用例.md` | 测试策略、用例设计 | 🧪 **每个里程碑测试** |
| **核心流程图** | `@cursor doc/运行逻辑（核心流程图）.md` | 业务流程可视化 | 💼 **M3-M5 业务逻辑** |
| **部署运维** | `@cursor doc/部署与运维.md` | 容器化、K8s配置 | 🚀 **M8 部署阶段** |

---

## 🎯 开发阶段文档使用指南

### 🛠️ **M0: 开发基础搭建**
**AI任务**: 创建项目结构、配置开发环境

#### 📖 必读文档:
- `@cursor doc/后端开发计划.md` (M0章节) - 详细任务清单
- `@cursor doc/技术栈.md` - Python、FastAPI技术要求
- `@cursor doc/开发规范.md` - 编码标准和工具配置

#### 🎯 关键任务:
```bash
# AI执行任务示例
1. 创建项目目录结构 (参考: 后端开发计划.md M0.1)
2. 配置pyproject.toml (参考: 技术栈.md)
3. 设置FastAPI基础框架 (参考: 开发规范.md)
4. 配置开发工具链 (black, ruff, pytest)
```

### 🔐 **M1: 核心数据模型与认证**
**AI任务**: 建立数据模型基础和JWT认证体系

#### 📖 必读文档:
- `@cursor doc/database_design/README.md` - 完整数据库设计
- `@cursor doc/database_design/erd_diagram.md` - ERD关系图
- `@cursor doc/api_contracts/models/common_models.yaml` - 统一数据模型
- `@cursor doc/开发规范.md` (多租户隔离规范)

#### ⚠️ 多租户隔离规则:
```python
# 🚨 CRITICAL: 所有数据操作必须包含tenant_id
# ❌ 错误示例
def get_sessions(): 
    return db.query(Session).all()

# ✅ 正确示例  
def get_sessions(tenant_id: UUID):
    return db.query(Session).filter(Session.tenant_id == tenant_id).all()
```

### 🏢 **M2: 租户管理系统**
**AI任务**: 实现租户CRUD、配置管理和资源隔离

#### 📖 必读文档:
- `@cursor doc/api_contracts/saas_platform_api.yaml` - 租户API规范
- `@cursor doc/功能说明.md` (租户管理功能)
- `@cursor doc/测试用例.md` (租户管理测试场景)

### 💬 **M3: 会话与消息管理**
**AI任务**: 实现完整的会话生命周期和消息处理

#### 📖 必读文档:
- `@cursor doc/algorithms/session_management/session_allocation.md` - 会话分配算法
- `@cursor doc/运行逻辑（核心流程图）.md` - 消息处理流程
- `@cursor doc/api_contracts/saas_platform_api.yaml` (消息API部分)

### 🤖 **M4: LLM推理与智能化**
**AI任务**: 集成LLM服务，实现智能客服功能

#### 📖 必读文档:
- `@cursor doc/功能说明.md` (LLM推理部分)
- `@cursor doc/algorithms/` (上下文管理算法)
- `@cursor doc/架构说明.md` (LLM编排架构)

### 🔗 **M5: AstrBot实例通信**
**AI任务**: 实现SaaS平台与AstrBot实例的双向通信

#### 📖 必读文档:
- `@cursor doc/api_contracts/astrbot_webhook_api.yaml` - Webhook API规范
- `@cursor doc/架构说明.md` (实例通信架构)
- `@cursor doc/运行逻辑（核心流程图）.md` (实例交互流程)

---

## 🤖 AI任务执行模式

### 📏 **文件长度限制原则** ⭐ **新增**

> **核心原则**: 优化AI理解能力，提高代码质量和可维护性

#### 🎯 文件行数标准
```python
# ✅ 推荐文件大小 (适合AI处理)
- 服务类 (Service): 200-400行
- API路由 (Router): 100-300行  
- 数据模型 (Model): 50-200行
- 工具函数 (Utils): 100-250行
- 配置文件 (Config): 50-150行

# ⚠️ 警告阈值
- 单文件超过500行需要Review
- 超过800行必须重构拆分

# ❌ 禁止模式
- 单文件超过1000行
- "上帝类"包含过多职责
```

#### 🔄 模块化拆分策略

**1. 服务层按职责拆分**
```python
# ❌ 错误 - 单一巨大服务 (AI难以理解)
class MessageService:  # 1500+ 行
    async def create_message()
    async def update_message()
    async def delete_message()
    async def send_notification()
    async def handle_ai_response()
    async def process_attachments()
    # ... 过多职责

# ✅ 正确 - 职责分离 (AI易于处理)
# app/services/message/core_service.py (300行)
class MessageService:
    async def create_message()
    async def update_message()
    async def delete_message()

# app/services/message/notification_service.py (200行)
class MessageNotificationService:
    async def send_real_time_notification()
    async def send_email_notification()

# app/services/message/ai_service.py (250行)
class MessageAIService:
    async def process_with_llm()
    async def generate_summary()
```

**2. 推荐的模块拆分模式**
```python
# 大型业务模块的标准拆分
saas-platform/app/services/session/
├── __init__.py
├── core_service.py           # 核心CRUD (300行)
├── lifecycle_service.py      # 生命周期管理 (250行)  
├── analytics_service.py      # 数据分析 (200行)
└── integration_service.py    # 第三方集成 (180行)
```

### 📝 **标准AI提示词格式**
```markdown
## 🤖 AI任务: 在 {文件路径} 中实现 {具体功能}

### 📋 模块化要求: ⭐ **新增**
- [ ] 单文件控制在400行以内
- [ ] 职责单一，符合SRP原则
- [ ] 如需超过400行，请拆分子模块

### 📚 上下文参考:
- 核心设计: @cursor doc/{核心设计文档}
- API规范: @cursor doc/api_contracts/{相关API文件}
- 数据模型: @cursor doc/api_contracts/models/common_models.yaml
- 开发规范: @cursor doc/开发规范.md

### 🚨 多租户隔离要求:
确保所有数据操作都包含tenant_id过滤

### ✅ 验收标准:
- [ ] 功能正常工作
- [ ] 包含必要的错误处理  
- [ ] 通过单元测试
- [ ] 符合多租户隔离要求
- [ ] **代码行数 ≤ 400行** ⭐ **新增**
```

### 🔧 **文件拆分AI提示词模板** ⭐ **新增**
```markdown
## 🔄 重构任务: 拆分过长文件

当前文件: {file_path} (当前: {current_lines}行)

### 📋 拆分要求:
1. 识别不同职责边界
2. 按功能创建子模块
3. 保持接口兼容性
4. 目标: 每个文件 ≤ 400行

### 🎯 拆分示例:
{current_file} → 
├── {module_1}.py (核心功能, ~300行)
├── {module_2}.py (辅助功能, ~250行)  
└── {module_3}.py (工具函数, ~200行)

### ✅ 验收标准:
- [ ] 原有功能完全保持
- [ ] 导入路径正确更新
- [ ] 每个子模块职责单一
- [ ] 所有测试依然通过
```

### 🔄 **迭代开发模式**
1. **明确小任务** (30分钟内完成)
2. **检查文件大小** ⭐ **新增** (使用 `scripts/check_file_length.py`)
3. **AI生成代码** (基于文档指导)
4. **人工审查** (检查多租户隔离、错误处理、文件长度)
5. **运行测试** (单元测试 + 集成测试)
6. **质量验证** (代码格式化、类型检查)
7. **下一任务** (迭代推进)

### 🎯 **AI协同最佳实践** ⭐ **新增**

**1. 文件引用策略**
```markdown
# ✅ 为AI提供精确上下文 (小文件，AI易理解)
@cursor saas-platform/app/services/message/core_service.py  # 300行
@cursor saas-platform/app/schemas/message_schemas.py       # 150行
@cursor doc/api_contracts/models/message_models.yaml       # 规范定义

# ❌ 避免引用巨大文件 (AI理解困难)
# @cursor saas-platform/app/services/giant_service.py  # 1500行
```

**2. 任务拆分技巧**
```markdown
# ✅ 小任务，清晰目标
"在 message_core_service.py 中添加软删除功能"

# ❌ 大任务，模糊范围  
"完善整个消息系统"
```

**3. 质量检查工具**
```bash
# 在开发过程中定期运行
python scripts/check_file_length.py saas-platform --max-lines 500

# CI/CD集成
python scripts/check_file_length.py saas-platform --ci
```

---

## 🎯 关键设计原则

### 🔐 **多租户隔离 (CRITICAL)**
- 所有数据模型必须包含`tenant_id`字段
- 所有数据查询必须包含租户过滤条件
- API端点必须验证租户权限

### 🛡️ **错误处理标准**
- 使用结构化异常处理
- 包含详细的错误日志记录
- 返回标准化错误响应格式

### ⚡ **异步优先**
- 所有I/O操作使用async/await
- 数据库操作使用SQLAlchemy异步模式
- HTTP请求使用httpx异步客户端

### 🧪 **测试驱动**
- 每个功能点都有对应的单元测试
- API端点都有集成测试
- 关键业务流程有端到端测试

---

## 📊 文档交叉引用索引

### 🔗 **核心概念定位表**

| 概念/实体 | 主要定义文档 | 补充参考文档 | AI开发使用 |
|-----|----|----|---|
| **租户(Tenant)** | `database_design/erd_diagram.md` | `api_contracts/models/common_models.yaml` | M1-M2阶段 |
| **会话(Session)** | `database_design/erd_diagram.md` | `algorithms/session_management/` | M3阶段 |
| **消息(Message)** | `api_contracts/models/common_models.yaml` | `运行逻辑（核心流程图）.md` | M3阶段 |
| **用户(User)** | `database_design/erd_diagram.md` | `开发规范.md`(认证部分) | M1阶段 |
| **LLM配置** | `功能说明.md` | `架构说明.md` | M4阶段 |

---

## ⚠️ 开发注意事项

### 🚨 **必须遵守的规则**
1. **多租户隔离**: 永远不要忘记tenant_id过滤
2. **类型安全**: 所有函数都要有完整的类型注解
3. **异常处理**: 每个service方法都要有异常处理
4. **测试优先**: 功能代码和测试代码同步开发
5. **文档引用**: 不确定设计时，优先查阅相关设计文档

### 💡 **AI开发最佳实践**
- 每次任务开始前，先查阅相关设计文档
- 实现功能时，参考统一数据模型定义
- 编写代码时，遵循项目编码规范
- 完成功能后，立即编写对应测试
- 遇到设计冲突时，以最新的设计文档为准

---

**文档版本**: v1.0  
**更新时间**: 2024年  
**维护原则**: 与开发进度同步更新，确保AI指导的准确性 