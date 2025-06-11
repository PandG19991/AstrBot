# 🤖 AstrBot SaaS Platform - AI开发协同指南

## 📋 项目核心信息

### 🎯 项目背景
基于 `@cursor doc/README.md` 和 `@cursor doc/架构说明.md`，AstrBot SaaS Platform是将单体AstrBot改造为多租户SaaS平台的核心项目。

### 🏗️ 核心架构原则
参考 `@cursor doc/架构说明.md` 中的设计：

- **多租户架构**: 租户级数据隔离，共享应用实例
- **微服务设计**: SaaS平台 + AstrBot实例 双向通信  
- **异步优先**: FastAPI + SQLAlchemy 2.0 + PostgreSQL
- **AI驱动**: LLM编排服务，支持多种AI模型

## 🎯 AI开发核心约束

### 🚨 **CRITICAL - 多租户隔离**
**所有数据操作必须包含tenant_id检查**

```python
# ❌ 绝对禁止 - 缺少租户隔离
def get_sessions():
    return db.query(Session).all()

# ✅ 强制模式 - 包含租户隔离
def get_sessions(tenant_id: UUID):
    return db.query(Session).filter(Session.tenant_id == tenant_id).all()
```

### ⚡ **异步优先原则**
- 所有I/O操作使用 `async/await`
- 数据库操作使用SQLAlchemy异步模式
- HTTP请求使用httpx异步客户端

### 🛡️ **错误处理标准**
```python
# 结构化异常处理模式
try:
    result = await some_operation()
    logger.info("operation_success", tenant_id=tenant_id, operation="xxx")
    return result
except SpecificError as e:
    logger.error("operation_failed", tenant_id=tenant_id, error=str(e))
    raise HTTPException(status_code=400, detail="Specific error message")
```

## 📚 文档引用体系

### 🎯 **核心设计文档** (AI开发必读)
- **项目概述**: `@cursor doc/README.md`
- **系统架构**: `@cursor doc/架构说明.md`
- **API契约**: `@cursor doc/api_contracts/README.md`
- **数据库设计**: `@cursor doc/database_design/README.md`
- **算法设计**: `@cursor doc/algorithms/README.md`
- **开发计划**: `@cursor doc/后端开发计划.md`

### 📊 **详细规范文档**
- **功能说明**: `@cursor doc/功能说明.md`
- **开发规范**: `@cursor doc/开发规范.md`
- **测试用例**: `@cursor doc/测试用例.md`
- **部署运维**: `@cursor doc/部署与运维.md`

## 🤖 AI任务执行模式

### 📝 **标准提示词格式**
```markdown
## 任务: 在 {文件路径} 中实现 {具体功能}

## 参考文档:
- @cursor doc/{相关设计文档}
- @cursor doc/api_contracts/models/common_models.yaml (统一数据模型)

## 验收标准:
- [ ] 包含tenant_id过滤 (多租户隔离)
- [ ] 使用async/await (异步优先)  
- [ ] 完整错误处理和日志
- [ ] 符合API契约规范
```

### 🔄 **迭代开发模式**
1. **明确小任务** (30分钟内完成)
2. **AI生成代码** (基于文档指导)
3. **人工审查** (检查多租户隔离、错误处理)
4. **运行测试** (单元测试 + 集成测试)
5. **质量验证** (代码格式化、类型检查)

## 🎯 关键设计原则

### 🔐 **多租户隔离 (CRITICAL)**
- 所有数据模型必须包含`tenant_id`字段
- 所有数据查询必须包含租户过滤条件
- API端点必须验证租户权限

### 🧪 **测试驱动**
- 每个功能点都有对应的单元测试
- API端点都有集成测试
- 关键业务流程有端到端测试

---

## ⚠️ 开发注意事项

### 🚨 **必须遵守的规则**
1. **多租户隔离**: 永远不要忘记tenant_id过滤
2. **类型安全**: 所有函数都要有完整的类型注解
3. **异常处理**: 每个service方法都要有异常处理
4. **测试优先**: 功能代码和测试代码同步开发

### 💡 **AI开发最佳实践**
- 每次任务开始前，先查阅相关设计文档
- 实现功能时，参考统一数据模型定义
- 编写代码时，遵循项目编码规范
- 完成功能后，立即编写对应测试

---

**AI协同版本**: v1.0  
**核心原则**: 安全第一，多租户隔离零容忍违规 