# AstrBot SaaS Platform

## 📋 项目简介

AstrBot SaaS Platform是一个多租户智能客服SaaS平台，基于原有的单体AstrBot系统改造而成。该平台支持多个企业用户独立使用智能客服服务，提供完整的SaaS解决方案。

## 🏗️ 核心架构

- **多租户架构**: 租户级数据隔离，共享应用实例
- **微服务设计**: SaaS平台 + AstrBot实例 双向通信
- **异步优先**: FastAPI + SQLAlchemy 2.0 + PostgreSQL
- **AI驱动**: LLM编排服务，支持多种AI模型

## 🚀 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 14+
- Redis 6+

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/astrbot/saas-platform.git
cd saas-platform
```

2. **创建虚拟环境**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **安装依赖**
```bash
pip install -e ".[dev]"
```

4. **配置环境变量**
```bash
copy env.example .env
# 编辑 .env 文件，配置数据库等信息
```

5. **初始化数据库**
```bash
alembic upgrade head
```

6. **启动开发服务器**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📁 项目结构

```
saas-platform/
├── app/                    # 主应用目录
│   ├── api/               # API层
│   │   ├── v1/           # API v1版本
│   │   └── deps/         # 依赖注入
│   ├── core/             # 核心功能
│   │   ├── auth/         # 认证模块
│   │   ├── config/       # 配置管理
│   │   └── database/     # 数据库连接
│   ├── models/           # 数据模型
│   ├── schemas/          # Pydantic模式
│   ├── services/         # 业务逻辑
│   └── utils/            # 工具函数
├── tests/                 # 测试目录
│   ├── unit/             # 单元测试
│   ├── integration/      # 集成测试
│   └── e2e/              # 端到端测试
├── alembic/              # 数据库迁移
├── docs/                 # 文档
└── scripts/              # 脚本工具
```

## 🛠️ 开发指南

### 多租户隔离原则

⚠️ **重要**: 所有数据操作必须包含租户隔离

```python
# ❌ 错误 - 缺少租户隔离
def get_sessions():
    return db.query(Session).all()

# ✅ 正确 - 包含租户隔离
def get_sessions(tenant_id: UUID):
    return db.query(Session).filter(Session.tenant_id == tenant_id).all()
```

### 代码规范

- 使用 `black` 进行代码格式化
- 使用 `ruff` 进行代码检查
- 使用 `mypy` 进行类型检查
- 所有函数必须有完整的类型注解

### 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=app tests/
```

## 📖 API文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🚀 部署

### Docker部署

```bash
# 构建镜像
docker build -t astrbot-saas-platform .

# 运行容器
docker run -p 8000:8000 astrbot-saas-platform
```

### 生产环境

详细的部署指南请参考: [部署文档](docs/deployment.md)

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 提交Pull Request

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 🔗 相关链接

- [项目文档](https://docs.astrbot.com)
- [API文档](https://api.astrbot.com/docs)
- [问题反馈](https://github.com/astrbot/saas-platform/issues)

## 📧 联系我们

- 邮箱: team@astrbot.com
- 官网: https://astrbot.com 