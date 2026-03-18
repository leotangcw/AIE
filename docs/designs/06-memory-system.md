# 记忆系统设计

**版本**: v1.0
**更新日期**: 2026-03-08
**文件路径**: `backend/modules/agent/memory.py`

---

## 1. 模块概述

记忆系统是 AIE 的长期记忆子系统，提供基于文件的行式记忆存储、关键词搜索、LLM 驱动的对话自动总结。

### 核心功能
- 行式记忆存储（`MEMORY.md`）
- 关键词搜索（支持 OR/AND 模式）
- LLM 驱动的对话总结
- 面向 Agent 的记忆工具

---

## 2. 存储格式

### 文件格式

记忆存储在工作空间的 `memory/MEMORY.md` 文件中，每行一条记忆：

```
日期 | 来源 | 内容事项 1；事项 2；事项 3
```

### 字段说明

| 字段 | 格式 | 说明 |
|------|------|------|
| 日期 | `YYYY-MM-DD` | 记忆写入日期 |
| 来源 | 字符串 | 记忆来源渠道标识 |
| 内容 | 中文分号分隔 | 一条或多条事项 |

### 来源标识

| 来源 | 说明 |
|------|------|
| `web-chat` | Web UI 对话 |
| `telegram` | Telegram 渠道 |
| `dingtalk` | 钉钉渠道 |
| `feishu` | 飞书渠道 |
| `qq` | QQ 渠道 |
| `cron` | 定时任务 |
| `auto-overflow` | 上下文滚动压缩自动写入 |
| `system` | 系统自动写入 |

### 示例

```
2026-02-15|web-chat|用户询问天气 API 方案；决定使用 OpenWeatherMap；缓存策略选 Redis TTL=3600s
2026-02-15|telegram|用户要求每天早上 9 点发送日报；已创建 cron 任务
2026-02-14|web-chat|项目使用 Vue3+TypeScript 前端；后端 FastAPI+SQLAlchemy
```

---

## 3. 核心组件

### 3.1 MemoryStore

**文件**: `backend/modules/agent/memory.py`

#### 职责
- 记忆文件读写
- 关键词搜索
- 记忆管理

#### 核心方法

```python
class MemoryStore:
    def __init__(self, memory_dir: Path):
        """初始化记忆存储"""

    def append_entry(source: str, content: str) -> int:
        """追加一条记忆，返回行号"""

    def read_lines(start: int, end: int = None) -> str:
        """按行号读取（1-based）"""

    def search(keywords: list[str], max_results: int = 15,
               match_mode: str = "or") -> str:
        """关键词搜索"""

    def delete_lines(line_numbers: list[int]) -> int:
        """删除指定行"""

    def get_recent(count: int = 10) -> str:
        """获取最近 N 条"""

    def get_stats() -> dict:
        """统计信息"""

    def read_all() -> str:
        """读取全部内容"""

    def write_all(content: str):
        """覆盖写入"""
```

### 3.2 ConversationSummarizer

**文件**: `backend/modules/agent/memory.py`

#### 职责
- 使用 LLM 总结对话
- 生成一行记忆条目

#### 核心方法

```python
class ConversationSummarizer:
    def __init__(self, provider, char_limit: int = 2000):
        """初始化总结器"""

    async def summarize_conversation(
        messages: list,
        previous_summary: str = ""
    ) -> str:
        """异步总结对话"""

    def should_summarize(
        messages: list,
        message_threshold: int = 20,
        char_threshold: int = 10000
    ) -> bool:
        """判断是否需要总结"""
```

### 3.3 MessageAnalyzer

**文件**: `backend/modules/agent/analyzer.py`

#### 职责
- 消息预处理
- 寒暄过滤

#### 寒暄过滤规则

```python
_SKIP_PREFIXES = (
    "好的", "知道了", "明白", "收到", "谢谢", "好", "行",
    "嗯", "哦", "OK", "嗯嗯", "哈哈", "呵呵", "嘻嘻",
    "thanks", "thx", "yes", "no", "cool", "nice",
)

# 过滤规则：长度 ≤ 8 且匹配前缀
```

---

## 4. 记忆工具

**文件**: `backend/modules/tools/memory_tool.py`

### 4.1 memory_write

写入记忆：

```json
{
  "name": "memory_write",
  "parameters": {
    "content": "用户偏好 Python 开发；项目使用 Vue3 前端"
  }
}
```

### 4.2 memory_search

搜索记忆：

```json
{
  "name": "memory_search",
  "parameters": {
    "keywords": "python fastapi",
    "max_results": 15,
    "match_mode": "or"
  }
}
```

### 4.3 memory_read

读取记忆：

```json
{
  "name": "memory_read",
  "parameters": {
    "start_line": 40,
    "end_line": 45
  }
}
```

---

## 5. API 接口

**文件**: `backend/api/memory.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/memory/long-term` | GET | 读取全部记忆 |
| `/api/memory/long-term` | PUT | 覆盖写入记忆 |
| `/api/memory/stats` | GET | 获取统计信息 |
| `/api/memory/recent` | GET | 获取最近记忆 |
| `/api/memory/search` | POST | 搜索记忆 |

---

## 6. 会话总结流程

```
用户点击 🧠 按钮
  │
  ▼
POST /api/chat/sessions/{id}/summarize
  │
  ▼
获取会话消息 → MessageAnalyzer.format()
  │
  ▼
LLM 生成总结 (temperature=0.3)
  │
  ▼
MemoryStore.append_entry(source, summary)
  │
  ▼
追加到 MEMORY.md
```

---

## 7. 上下文滚动压缩

当对话消息数超过 `max_history_messages` 时，自动将溢出的旧消息总结写入 MEMORY.md：

```
发送消息前
  │
  ▼
summarize_overflow()
  │
  ├─ 计算溢出消息
  ├─ 过滤已总结的消息 (last_summarized_msg_id)
  ├─ LLM 总结
  ├─ 写入 MEMORY.md (source="auto-overflow")
  └─ 更新 last_summarized_msg_id
```

---

## 8. 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 记忆目录 | `workspace/memory/` | 记忆文件存储目录 |
| 记忆文件 | `MEMORY.md` | 记忆存储文件名 |
| 搜索默认条数 | `15` | 搜索默认返回条数 |
| 搜索默认模式 | `"or"` | OR/AND 匹配模式 |
| 总结字符限制 | `2000` | ConversationSummarizer 限制 |
| 总结消息阈值 | `20` | 触发自动总结的消息数 |
| 总结字符阈值 | `10000` | 触发自动总结的总字符数 |
| 保留最近消息 | `10` | 总结时保留最近 N 条 |
| LLM 温度 | `0.3` | 总结时使用的温度 |

---

## 9. 前端集成

### 组件结构

```
frontend/src/modules/memory/
├── MemoryPanel.vue      # 记忆面板
├── MemoryViewer.vue     # 记忆查看器
├── MemoryEditor.vue     # 记忆编辑器
└── MemorySearch.vue     # 记忆搜索
```

### Store

```typescript
const memoryStore = useMemoryStore()

// 加载记忆
await memoryStore.loadLongTermMemory()

// 保存记忆
await memoryStore.saveLongTermMemory(content)

// 本地搜索
const results = memoryStore.searchMemory("python fastapi")
```

---

## 10. 待办事项 (TODO)

### 高优先级
- [ ] 优化记忆压缩算法
- [ ] 添加记忆重要性评分

### 中优先级
- [ ] 支持语义搜索（可选 Embedding）
- [ ] 记忆关联图谱

### 低优先级
- [ ] 记忆版本控制
- [ ] 记忆导出/导入
