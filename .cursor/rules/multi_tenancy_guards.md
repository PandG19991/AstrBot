# 🛡️ 多租户隔离守则 - CRITICAL AI开发约束

## 🚨 核心原则：数据隔离绝对优先

**多租户隔离是系统安全的生命线，违反此规则可能导致数据泄露**

---

## 🔐 强制规则清单

### ✅ **规则1: 所有数据模型必须包含tenant_id**

```python
# ✅ 正确的数据模型设计
class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey('tenants.id'), nullable=False)  # 🚨 必须字段
    customer_id = Column(String(100), nullable=False)
    # ... 其他字段

# ❌ 错误 - 缺少tenant_id
class BadSession(Base):
    id = Column(UUID, primary_key=True)
    customer_id = Column(String(100))
    # 缺少tenant_id - 数据将无法隔离
```

### ✅ **规则2: 所有数据查询必须包含租户过滤**

```python
# ✅ 正确的数据查询方式
async def get_user_sessions(db: AsyncSession, tenant_id: UUID, user_id: UUID):
    result = await db.execute(
        select(Session)
        .where(Session.tenant_id == tenant_id)  # 🚨 必须过滤
        .where(Session.user_id == user_id)
    )
    return result.scalars().all()

# ❌ 错误 - 缺少租户过滤
async def get_user_sessions_bad(db: AsyncSession, user_id: UUID):
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)  # 可能访问其他租户数据
    )
    return result.scalars().all()
```

### ✅ **规则3: Service层方法强制要求tenant_id参数**

```python
# ✅ 正确的Service设计
class MessageService:
    async def create_message(
        self, 
        db: AsyncSession,
        tenant_id: UUID,  # 🚨 必须参数
        message_data: MessageCreate
    ) -> Message:
        message = Message(
            tenant_id=tenant_id,  # 确保设置租户ID
            **message_data.dict()
        )
        db.add(message)
        await db.commit()
        return message
    
    async def get_session_messages(
        self,
        db: AsyncSession, 
        tenant_id: UUID,  # 🚨 必须参数
        session_id: UUID
    ) -> List[Message]:
        # 先验证session属于该租户
        session = await db.execute(
            select(Session)
            .where(Session.id == session_id)
            .where(Session.tenant_id == tenant_id)  # 🚨 租户验证
        )
        if not session.scalar_one_or_none():
            raise SessionNotFoundError(f"Session {session_id} not found for tenant {tenant_id}")
        
        # 然后查询消息
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .where(Message.tenant_id == tenant_id)  # 🚨 双重保险
            .order_by(Message.created_at.desc())
        )
        return result.scalars().all()

# ❌ 错误的Service设计  
class BadMessageService:
    async def create_message(self, db: AsyncSession, message_data: MessageCreate):
        # 缺少tenant_id参数和设置
        message = Message(**message_data.dict())
        db.add(message)
        await db.commit()
        return message
```

### ✅ **规则4: API端点必须验证租户权限**

```python
# ✅ 正确的API端点设计
@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),  # 🚨 租户依赖
    db: AsyncSession = Depends(get_db),
    message_service: MessageService = Depends()
):
    """获取会话消息 - 确保租户隔离"""
    messages = await message_service.get_session_messages(
        db=db,
        tenant_id=current_tenant.id,  # 🚨 使用当前租户ID
        session_id=session_id
    )
    return messages

# ❌ 错误的API设计
@router.get("/sessions/{session_id}/messages")  
async def get_session_messages_bad(
    session_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    # 没有租户验证，可能访问其他租户数据
    result = await db.execute(
        select(Message).where(Message.session_id == session_id)
    )
    return result.scalars().all()
```

### ✅ **规则5: 依赖注入中的租户上下文提取**

```python
# ✅ 正确的租户依赖实现
async def get_current_tenant(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """提取当前请求的租户上下文"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")  # 🚨 从token中提取租户ID
        
        if user_id is None or tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # 验证租户存在且用户属于该租户
        result = await db.execute(
            select(Tenant)
            .join(User)
            .where(Tenant.id == tenant_id)
            .where(User.id == user_id)
            .where(User.tenant_id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if tenant is None:
            raise HTTPException(status_code=401, detail="Tenant not found")
            
        return tenant
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ✅ 可选：租户ID提取的简化版本
async def get_current_tenant_id(
    current_tenant: Tenant = Depends(get_current_tenant)
) -> UUID:
    """简化的租户ID提取依赖"""
    return current_tenant.id
```

---

## 🎯 常见违规模式与修正

### ❌ **违规模式1: 忘记租户过滤的聚合查询**

```python
# ❌ 错误 - 统计查询缺少租户过滤
async def get_message_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count(Message.id)))
    return result.scalar()

# ✅ 修正
async def get_message_count(db: AsyncSession, tenant_id: UUID) -> int:
    result = await db.execute(
        select(func.count(Message.id))
        .where(Message.tenant_id == tenant_id)  # 🚨 必须过滤
    )
    return result.scalar()
```

### ❌ **违规模式2: 批量操作缺少租户验证**

```python
# ❌ 错误 - 批量删除没有租户限制
async def delete_old_messages(db: AsyncSession, days: int):
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    await db.execute(
        delete(Message).where(Message.created_at < cutoff_date)
    )

# ✅ 修正
async def delete_old_messages(db: AsyncSession, tenant_id: UUID, days: int):
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    await db.execute(
        delete(Message)
        .where(Message.tenant_id == tenant_id)  # 🚨 租户限制
        .where(Message.created_at < cutoff_date)
    )
```

### ❌ **违规模式3: 关联查询忘记多表租户过滤**

```python
# ❌ 错误 - JOIN查询只过滤了一张表
async def get_session_with_messages(db: AsyncSession, tenant_id: UUID, session_id: UUID):
    result = await db.execute(
        select(Session, Message)
        .join(Message)
        .where(Session.tenant_id == tenant_id)  # 只过滤了Session表
        .where(Session.id == session_id)
    )
    return result.all()

# ✅ 修正
async def get_session_with_messages(db: AsyncSession, tenant_id: UUID, session_id: UUID):
    result = await db.execute(
        select(Session, Message)
        .join(Message)
        .where(Session.tenant_id == tenant_id)   # 🚨 两张表都要过滤
        .where(Message.tenant_id == tenant_id)   # 🚨 双重保险
        .where(Session.id == session_id)
    )
    return result.all()
```

---

## 🔧 AI开发检查清单

### 📋 **每次编写代码前必须检查**

- [ ] **数据模型**: 是否包含`tenant_id`字段？
- [ ] **查询语句**: 是否包含`WHERE tenant_id = ?`过滤条件？
- [ ] **Service方法**: 是否要求`tenant_id`参数？
- [ ] **API端点**: 是否使用`get_current_tenant`依赖？
- [ ] **批量操作**: 是否限制在当前租户范围内？
- [ ] **关联查询**: 是否所有表都应用了租户过滤？

### 🧪 **测试用例必须覆盖**

```python
# ✅ 多租户隔离测试示例
async def test_tenant_isolation():
    """测试租户隔离 - 核心安全测试"""
    
    # 创建两个不同租户的数据
    tenant1 = await create_test_tenant("tenant1")
    tenant2 = await create_test_tenant("tenant2")
    
    session1 = await create_test_session(tenant_id=tenant1.id)
    session2 = await create_test_session(tenant_id=tenant2.id)
    
    # 确保租户1无法访问租户2的数据
    with pytest.raises(SessionNotFoundError):
        await message_service.get_session_messages(
            db=db,
            tenant_id=tenant1.id,  # 租户1的ID
            session_id=session2.id  # 但尝试访问租户2的session
        )
```

---

## ⚠️ 特殊场景处理

### 🔧 **系统级操作的租户处理**

```python
# ✅ 系统管理员操作 - 明确标注跨租户权限
async def system_cleanup_expired_sessions(
    db: AsyncSession,
    admin_user: User,  # 必须是系统管理员
    days: int
) -> Dict[str, int]:
    """系统级清理 - 需要super admin权限"""
    
    # 验证超级管理员权限
    if not admin_user.is_super_admin:
        raise PermissionDeniedError("Only super admin can perform system-wide operations")
    
    # 系统级操作可以跨租户，但要明确记录
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # 按租户统计清理结果
    cleanup_stats = {}
    for tenant in await get_all_tenants(db):
        deleted_count = await db.execute(
            delete(Session)
            .where(Session.tenant_id == tenant.id)  # 仍然按租户处理
            .where(Session.updated_at < cutoff_date)
            .where(Session.status == SessionStatus.CLOSED)
        )
        cleanup_stats[tenant.name] = deleted_count.rowcount
    
    # 记录系统操作日志
    await log_system_operation(
        admin_user_id=admin_user.id,
        operation="cleanup_expired_sessions",
        affected_tenants=list(cleanup_stats.keys())
    )
    
    return cleanup_stats
```

---

## 💡 AI提示词增强

当AI生成涉及数据操作的代码时，自动添加以下检查：

```markdown
## 多租户隔离检查
🚨 请确认以下代码符合多租户隔离要求：

1. **数据模型**: 是否包含tenant_id字段？
2. **查询过滤**: 是否添加了tenant_id过滤条件？
3. **API端点**: 是否验证了租户权限？
4. **Service方法**: 是否要求tenant_id参数？

如果不符合，请重新生成符合多租户隔离原则的代码。
```

---

**文档版本**: v1.0  
**更新时间**: 2024年  
**遵守级别**: 🚨 CRITICAL - 违反将导致安全漏洞 