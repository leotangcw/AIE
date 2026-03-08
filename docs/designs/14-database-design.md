# 数据库设计文档

**版本**: v1.0
**更新日期**: 2026-03-08

---

## 1. 数据库概述

### 1.1 数据库选型

| 环境 | 数据库 | 说明 |
|------|--------|------|
| 开发/轻量部署 | SQLite | 单文件，零配置 |
| 生产环境 | PostgreSQL | 高性能，支持并发 |

### 1.2 连接配置

```python
# SQLite
DATABASE_URL = "sqlite+aiosqlite:///data/aie.db"

# PostgreSQL
DATABASE_URL = "postgresql+asyncpg://user:password@host:5432/aie"
```

---

## 2. 数据模型总览

### 2.1 ER 图

```
┌─────────────────┐       ┌─────────────────┐
│    Session      │       │   Personality   │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ name            │       │ name            │
│ created_at      │       │ description     │
│ updated_at      │       │ traits          │
└────────┬────────┘       │ speaking_style  │
         │                │ is_builtin      │
         │ 1              │ is_active       │
         │                └─────────────────┘
         │
         │ N
┌────────▼────────┐
│    Message      │
├─────────────────┤
│ id (PK)         │
│ session_id (FK) │
│ role            │
│ content         │
│ timestamp       │
│ tool_calls      │
└─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│    CronJob      │       │     Setting     │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ name            │       │ key             │
│ cron_expression │       │ value           │
│ message         │       │ created_at      │
│ channel         │       │ updated_at      │
│ chat_id         │       └─────────────────┘
│ enabled         │
│ next_run        │       ┌─────────────────┐
│ created_at      │       │      Task       │
│ updated_at      │       ├─────────────────┤
└─────────────────┘       │ id (PK)         │
                          │ type            │
┌─────────────────┐       │ status          │
│ToolConversation │       │ progress        │
├─────────────────┤       │ result          │
│ id (PK)         │       │ error           │
│ session_id      │       │ created_at      │
│ tool_name       │       │ updated_at      │
│ arguments       │       └─────────────────┘
│ user_message    │
│ result          │
│ error           │
│ duration_ms     │
│ created_at      │
└─────────────────┘
```

---

## 3. 数据模型详解

### 3.1 Session (会话表)

**文件**: `backend/models/session.py`

```python
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan"
    )
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(64) | 会话唯一标识 |
| name | String(255) | 会话名称 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

**索引**:
- PRIMARY KEY (id)

### 3.2 Message (消息表)

**文件**: `backend/models/message.py`

```python
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    tool_calls: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True  # JSON 格式存储工具调用
    )

    # 关系
    session: Mapped["Session"] = relationship("Session", back_populates="messages")
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(64) | 消息唯一标识 |
| session_id | String(64) | 所属会话 ID |
| role | String(20) | 角色 (user/assistant/system) |
| content | Text | 消息内容 |
| timestamp | DateTime | 时间戳 |
| tool_calls | Text | 工具调用 (JSON 格式) |

**索引**:
- PRIMARY KEY (id)
- INDEX (session_id)
- INDEX (timestamp)

### 3.3 Personality (性格表)

**文件**: `backend/models/personality.py`

```python
class Personality(Base):
    __tablename__ = "personalities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    traits: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 数组
    speaking_style: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(64) | 性格唯一标识 |
| name | String(100) | 性格名称 |
| description | Text | 性格描述 |
| traits | Text | 特征列表 (JSON) |
| speaking_style | Text | 说话风格 |
| icon | String(50) | 图标名称 |
| is_builtin | Boolean | 是否内置 |
| is_active | Boolean | 是否激活 |

**内置性格**:
- grumpy (暴躁型)
- gentle (温柔型)
- humorous (幽默型)
- professional (专业型)
- cute (可爱型)

### 3.4 CronJob (定时任务表)

**文件**: `backend/models/cron_job.py`

```python
class CronJob(Base):
    __tablename__ = "cron_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(64) | 任务唯一标识 |
| name | String(255) | 任务名称 |
| cron_expression | String(100) | Cron 表达式 |
| message | Text | 执行消息 |
| channel | String(50) | 目标渠道 |
| chat_id | String(100) | 目标聊天 ID |
| enabled | Boolean | 是否启用 |
| next_run | DateTime | 下次运行时间 |

### 3.5 Task (后台任务表)

**文件**: `backend/models/task.py`

```python
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String(64) | 任务唯一标识 |
| type | String(50) | 任务类型 |
| status | String(20) | 状态 (pending/running/completed/failed) |
| progress | Integer | 进度 (0-100) |
| result | Text | 执行结果 |
| error | Text | 错误信息 |

### 3.6 Setting (设置表)

**文件**: `backend/models/setting.py`

```python
class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| key | String(255) | 配置键 (唯一) |
| value | Text | 配置值 |

### 3.7 ToolConversation (工具调用对话表)

**文件**: `backend/models/tool_conversation.py`

```python
class ToolConversation(Base):
    __tablename__ = "tool_conversations"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    user_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 自增主键 |
| session_id | String(64) | 会话 ID |
| tool_name | String(100) | 工具名称 |
| arguments | Text | 工具参数 (JSON) |
| user_message | Text | 用户消息 |
| result | Text | 执行结果 |
| error | Text | 错误信息 |
| duration_ms | Integer | 耗时 (毫秒) |

---

## 4. 数据库操作

### 4.1 初始化

**文件**: `backend/database.py`

```python
async def init_db() -> None:
    """初始化数据库"""
    from backend.models import (
        CronJob, Message, Personality, Session, Setting, Task, ToolConversation
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await init_personalities()
```

### 4.2 会话管理

```python
# 获取数据库会话
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# 获取会话工厂
def get_db_session_factory():
    return AsyncSessionLocal
```

### 4.3 常用查询

#### 获取会话列表

```python
async def get_sessions(db: AsyncSession) -> list[Session]:
    result = await db.execute(
        select(Session).order_by(Session.updated_at.desc())
    )
    return result.scalars().all()
```

#### 获取会话消息

```python
async def get_messages(
    db: AsyncSession,
    session_id: str,
    limit: int = 50,
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.timestamp.asc())
        .limit(limit)
    )
    return result.scalars().all()
```

#### 创建定时任务

```python
async def create_cron_job(
    db: AsyncSession,
    job_data: dict,
) -> CronJob:
    job = CronJob(**job_data)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job
```

---

## 5. 数据迁移

### 5.1 Alembic 配置

使用 Alembic 进行数据库迁移管理:

```bash
# 初始化 Alembic
alembic init alembic

# 创建新迁移
alembic revision -m "add new table"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 5.2 迁移示例

```python
"""add tool_conversations table

Revision ID: abc123
Revises: def456
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table(
        'tool_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('arguments', sa.Text(), nullable=False),
        sa.Column('user_message', sa.Text(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table('tool_conversations')
```

---

## 6. 性能优化

### 6.1 索引优化

```sql
-- 消息表时间索引
CREATE INDEX idx_messages_timestamp ON messages(timestamp);

-- 消息表会话索引
CREATE INDEX idx_messages_session_id ON messages(session_id);

-- 定时任务启用状态索引
CREATE INDEX idx_cron_jobs_enabled ON cron_jobs(enabled);

-- 定时任务下次运行时间索引
CREATE INDEX idx_cron_jobs_next_run ON cron_jobs(next_run);
```

### 6.2 查询优化

```python
# 使用预加载
async def get_session_with_messages(session_id: str):
    async with AsyncSessionLocal() as db:
        return await db.get(
            Session,
            session_id,
            options=selectinload(Session.messages)
        )

# 批量操作
async def bulk_insert_messages(messages: list[Message]):
    async with AsyncSessionLocal() as db:
        db.add_all(messages)
        await db.commit()
```

### 6.3 连接池配置

```python
# PostgreSQL 连接池
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # 连接池大小
    max_overflow=10,       # 最大溢出连接数
    pool_pre_ping=True,    # 连接前检查
    pool_recycle=3600,     # 连接回收时间
)
```

---

## 7. 待办事项 (TODO)

### 高优先级
- [ ] 添加数据备份功能
- [ ] 实现数据归档策略
- [ ] 添加数据库监控

### 中优先级
- [ ] 优化大表查询性能
- [ ] 实现读写分离
- [ ] 添加数据清理任务

### 低优先级
- [ ] 支持多数据库
- [ ] 实现分表策略
- [ ] 数据仓库集成
