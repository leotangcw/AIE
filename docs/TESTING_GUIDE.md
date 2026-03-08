# AIE 测试指南

> 本文档说明 AIE 项目的测试策略、测试框架和本地运行测试的方法。

---

## 📋 目录

- [测试策略](#测试策略)
- [测试框架](#测试框架)
- [运行测试](#运行测试)
- [编写测试](#编写测试)
- [测试覆盖率](#测试覆盖率)
- [CI 集成](#ci-集成)

---

## 🎯 测试策略

### 测试金字塔

```
        /\
       /  \
      / E2E \      端到端测试 (10%)
     /______\
    /        \
   / Integration\    集成测试 (20%)
  /______________\
 /                \
/    Unit Tests    \   单元测试 (70%)
--------------------
```

### 测试类型

| 类型 | 说明 | 工具 |
|------|------|------|
| 单元测试 | 测试单个函数/类 | pytest |
| 集成测试 | 测试模块间交互 | pytest + mock |
| 端到端测试 | 测试完整用户流程 | pytest + httpx |
| UI 测试 | 测试前端组件 | Vitest + Vue Test Utils |

---

## 🧪 测试框架

### 后端测试栈

```toml
# pytest 配置 (pyproject.toml)
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "e2e: marks tests as end-to-end tests",
]
asyncio_mode = "auto"
```

### 前端测试栈

```json
// frontend/package.json
{
  "devDependencies": {
    "vitest": "^1.0.0",
    "@vue/test-utils": "^2.4.0",
    "@testing-library/vue": "^8.0.0"
  },
  "scripts": {
    "test": "vitest",
    "test:coverage": "vitest --coverage"
  }
}
```

---

## ▶️ 运行测试

### 快速开始

```bash
# 运行所有测试
pytest

# 运行指定目录测试
pytest backend/tests/

# 运行指定文件测试
pytest backend/tests/test_agent.py

# 运行指定类测试
pytest backend/tests/test_agent.py::TestAgentLoop

# 运行指定函数测试
pytest backend/tests/test_agent.py::TestAgentLoop::test_process_message

# 运行并显示覆盖率
pytest --cov=backend --cov-report=html

# 运行测试并生成 XML 报告 (CI 用)
pytest --cov=backend --cov-report=xml --junitxml=test-results.xml
```

### 测试标记

```bash
# 只运行单元测试
pytest -m "not integration and not e2e"

# 只运行集成测试
pytest -m integration

# 跳过慢速测试
pytest -m "not slow"

# 只运行慢速测试
pytest -m slow
```

### 前端测试

```bash
cd frontend

# 运行所有测试
npm test

# 监视模式
npm run test:watch

# 生成覆盖率
npm run test:coverage

# 运行单个文件
npm run test -- tests/components/ChatWindow.test.ts
```

---

## ✍️ 编写测试

### 单元测试示例

```python
# backend/tests/test_memory.py
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.modules.agent.memory import MemoryStore


class TestMemoryStore:
    """MemoryStore 测试类"""

    @pytest.fixture
    def memory_store(self):
        """创建临时记忆存储"""
        with TemporaryDirectory() as tmpdir:
            store = MemoryStore(memory_dir=Path(tmpdir))
            yield store

    def test_append_entry(self, memory_store):
        """测试追加记忆条目"""
        line_number = memory_store.append_entry(
            source="test",
            content="测试记忆内容"
        )
        assert line_number == 1

    def test_read_lines(self, memory_store):
        """测试读取记忆行"""
        memory_store.append_entry("test", "内容 1")
        memory_store.append_entry("test", "内容 2")

        content = memory_store.read_lines(start=1, end=2)

        assert "内容 1" in content
        assert "内容 2" in content

    def test_search(self, memory_store):
        """测试关键词搜索"""
        memory_store.append_entry("test", "Python 开发经验")
        memory_store.append_entry("test", "JavaScript 开发经验")

        results = memory_store.search(keywords=["Python"])

        assert "Python" in results
        assert "JavaScript" not in results

    def test_delete_lines(self, memory_store):
        """测试删除记忆行"""
        memory_store.append_entry("test", "内容 1")
        memory_store.append_entry("test", "内容 2")

        deleted = memory_store.delete_lines(line_numbers=[1])
        assert deleted == 1

        content = memory_store.read_all()
        assert "内容 1" not in content
```

### 异步测试示例

```python
# backend/tests/test_agent.py
import pytest
from unittest.mock import AsyncMock, patch

from backend.modules.agent.loop import AgentLoop
from backend.modules.agent.config import AgentConfig


@pytest.mark.asyncio
async def test_process_message_async():
    """测试异步消息处理"""
    config = AgentConfig(model_name="test", api_key="test")
    loop = AgentLoop(config=config)

    with patch.object(loop, "_provider") as mock_provider:
        mock_provider.generate = AsyncMock(return_value={
            "content": "Hello!",
            "tool_calls": []
        })

        result = await loop.process_message("Hi")

        assert result["content"] == "Hello!"
        mock_provider.generate.assert_called_once()
```

### 集成测试示例

```python
# backend/tests/integration/test_chat_flow.py
import pytest
from httpx import AsyncClient

from backend.app import create_app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_flow():
    """测试完整聊天流程"""
    app = create_app()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # 1. 创建会话
        response = await ac.post("/api/chat/sessions", json={
            "name": "测试会话"
        })
        assert response.status_code == 200
        session_id = response.json()["id"]

        # 2. 发送消息
        response = await ac.post("/api/chat/send", json={
            "session_id": session_id,
            "message": "Hello"
        })
        assert response.status_code == 200

        # 3. 获取消息历史
        response = await ac.get(
            f"/api/chat/sessions/{session_id}/messages"
        )
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) > 0
```

### 前端组件测试示例

```typescript
// frontend/src/modules/chat/tests/ChatWindow.test.ts
import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'

import ChatWindow from '../components/ChatWindow.vue'

describe('ChatWindow', () => {
  it('renders messages correctly', () => {
    const messages = [
      { id: '1', role: 'user', content: 'Hello' },
      { id: '2', role: 'assistant', content: 'Hi!' }
    ]

    const wrapper = mount(ChatWindow, {
      props: {
        messages
      }
    })

    expect(wrapper.findAll('.message-item').length).toBe(2)
    expect(wrapper.text()).toContain('Hello')
    expect(wrapper.text()).toContain('Hi!')
  })

  it('emits send-message event when submitting', async () => {
    const wrapper = mount(ChatWindow)

    const input = wrapper.find('input[type="text"]')
    await input.setValue('Test message')
    await input.trigger('keyup', { key: 'Enter' })

    expect(wrapper.emitted('send-message')).toBeTruthy()
    expect(wrapper.emitted('send-message')?.[0]).toEqual(['Test message'])
  })
})
```

---

## 📊 测试覆盖率

### 覆盖率要求

| 模块类型 | 行覆盖率 | 分支覆盖率 |
|----------|---------|-----------|
| 核心模块 | ≥ 80% | ≥ 70% |
| API 层 | ≥ 70% | ≥ 60% |
| 工具函数 | ≥ 90% | ≥ 80% |
| UI 组件 | ≥ 60% | ≥ 50% |

### 生成覆盖率报告

```bash
# HTML 报告
pytest --cov=backend --cov-report=html
# 打开 htmlcov/index.html

# XML 报告 (CI 用)
pytest --cov=backend --cov-report=xml

# 终端详细报告
pytest --cov=backend --cov-report=term-missing

# 检查最低覆盖率
pytest --cov=backend --cov-fail-under=80
```

### 覆盖率配置

```ini
# .coveragerc
[run]
source = backend
omit =
    */tests/*
    */migrations/*
    */__init__.py
    */app.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
```

---

## 🔗 CI 集成

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: |
          pytest \
            --cov=backend \
            --cov-report=xml \
            --cov-report=html \
            --junitxml=test-results.xml \
            -v

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          flags: backend

      - name: Upload test results
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: test-results.xml
```

### 本地 CI 脚本

```bash
#!/bin/bash
# scripts/run_tests.sh

set -e

echo "🧪 Running AIE Tests..."

# Backend tests
echo "📦 Backend Tests"
pytest backend/tests/ \
    --cov=backend \
    --cov-report=term-missing \
    --cov-fail-under=75 \
    -v

# Frontend tests
echo "📦 Frontend Tests"
cd frontend && npm test -- --run

echo "✅ All tests passed!"
```

---

## 🐛 常见问题

### Mock 外部依赖

```python
from unittest.mock import patch, MagicMock

# Mock LLM API
with patch('backend.modules.providers.litellm_provider.litellm') as mock_litellm:
    mock_litellm.completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="test"))]
    )
    # 运行测试代码
```

### 测试数据库操作

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture
async def db_session():
    """创建测试数据库会话"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

    await engine.dispose()
```

### 测试 WebSocket

```python
import pytest
from fastapi.testclient import TestClient

def test_websocket_connection():
    """测试 WebSocket 连接"""
    client = TestClient(app)

    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_json({"type": "connect"})
        data = websocket.receive_json()
        assert data["type"] == "connected"
```

---

## 📖 参考资源

- [pytest 官方文档](https://docs.pytest.org/)
- [Vitest 官方文档](https://vitest.dev/)
- [测试最佳实践](https://docs.python-guide.org/writing/tests/)
