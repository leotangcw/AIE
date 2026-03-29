# SuperWorkers 企业知识学习模块 - 架构设计方案

> 日期: 2026-03-29
> 状态: Phase 1-4 全部实施完成

---

## 一、设计背景与目标

### 1.1 核心问题

AIE 作为企业级 AI 办公助手，当前缺乏系统性的"从企业知识中学习"能力：
- Agent 面对企业任务时完全从零出发，不主动利用已有知识
- 三套知识系统（KnowledgeRAG、KnowledgeHub、GraphRAG）割裂并存，无统一入口
- 缺少操作轨迹记录，无法从成功/失败中提炼经验
- ExperienceEngine 是空壳实现，不具备实际进化能力

### 1.2 设计目标

1. **知识驱动工作**: Agent 接到企业任务时，先查本地技能 → 查企业知识 → 整理参考资料 → 再执行
2. **统一知识入口**: KnowledgeHub 作为所有企业知识源的聚合管理入口
3. **基础设施下沉**: RAG/GraphRAG/数据库访问/向量检索等作为 AIE 基础能力层
4. **工作流可插拔**: 通过 SuperWorkers Plugin 注入企业工作规范，不写死在核心代码中
5. **全量轨迹记录**: 完整记录 Agent 工作过程，支持后续经验提炼
6. **谨慎技能进化**: 人工触发、审核后才发布新技能，避免自动扰动

### 1.3 与 Superpowers 的关系

| 维度 | Superpowers | SuperWorkers |
|------|-------------|--------------|
| 定位 | 开发流程规范 | 企业工作流规范 |
| 场景 | 编码、调试、审查、测试 | 知识检索、技能匹配、轨迹记录、经验进化 |
| 模式 | 同 - Plugin + Skills + Hooks | 同 - Plugin + Skills + Hooks |
| 触发 | Claude Code 自动发现 | AIE 系统提示词引导发现 |
| 技能性质 | 模板化（开发流程固定） | 指导性（企业场景多变） |

---

## 二、三层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: SuperWorkers Plugin                                │
│  "AIE 应该怎么干"                                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Workflow Skills (指导性规则)                         │    │
│  │  using-superworkers → 发现入口                       │    │
│  │  task-knowledge-review → 任务前知识审查              │    │
│  │  execution-standards → 执行过程规范                  │    │
│  │  trace-analyzer → 分析近期轨迹 (人工触发)            │    │
│  │  skill-distiller → 提炼新技能 (人工触发)             │    │
│  │  skill-refiner → 优化已有技能 (人工触发)             │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Hooks (事件驱动)                                    │    │
│  │  before_process → 轨迹记录启动                       │    │
│  │  tool_called → 工具调用记录                          │    │
│  │  tool_result → 工具结果记录                          │    │
│  │  after_process → 轨迹完成 + 效果记录                 │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: KnowledgeHub (知识源聚合层)                        │
│  "有哪些知识可用"                                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Connector 管理 (可插拔)                             │    │
│  │  ├── LocalConnector (本地文件/目录)                  │    │
│  │  ├── DatabaseConnector (SQL数据库, LLM生成查询)     │    │
│  │  ├── WebSearchConnector (网络搜索)                   │    │
│  │  ├── WikiConnector (企业Wiki/Confluence) [扩展]     │    │
│  │  ├── FeishuDocConnector (飞书文档) [扩展]            │    │
│  │  └── ... (按需扩展)                                  │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │  统一检索接口                                        │    │
│  │  retrieve(query, mode, source_ids) → KnowledgeResult │    │
│  │  支持: direct / vector / hybrid / llm / graph        │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 基础能力层 (Base Infrastructure)                   │
│  "底层能力，可被任何模块调用"                                │
│  ┌────────────┬────────────┬────────────┬────────────┐     │
│  │ VectorStore│  GraphRAG  │ Memory     │ WebSearch  │     │
│  │ (bge-small │ (LightRAG) │ (L0/L1/L2) │ (抓取/搜索)│     │
│  │ zh, FAISS) │            │            │            │     │
│  └────────────┴────────────┴────────────┴────────────┘     │
└─────────────────────────────────────────────────────────────┘

AIE Agent 可直接调用任何一层的能力，不仅限于上层调用下层。
```

### 2.1 各层职责边界

| 层 | 职责 | 谁调用 | 关键特征 |
|----|------|--------|----------|
| Layer 1 | 提供原子级能力（向量检索、图查询、DB查询、网页抓取） | Layer 2/3、Agent 直接调用 | 无业务逻辑，纯技术能力 |
| Layer 2 | 聚合管理知识源、提供统一检索入口 | Agent 通过工具调用、SuperWorkers 编排 | 面向知识管理，多源聚合 |
| Layer 3 | 定义工作流规范、记录轨迹、提炼经验 | 通过 Plugin 系统注入 | 面向工作方法，可配置可插拔 |

---

## 三、现有代码整合方案

### 3.1 KnowledgeRAG (agent/knowledge.py) → 废弃

**原因**: 自制 BM25 和词频向量（非语义 embedding）质量差，功能被 KnowledgeHub 完全覆盖。

**处理步骤**:
1. 保留 `KnowledgeSource`、`KnowledgeChunk`、`KnowledgeRef` 数据类（可迁移复用）
2. 删除 `RAGSkillRetriever`、`BM25Retriever`、`VectorRetriever`（自制实现）
3. 删除 `KnowledgeRAG` 类及其全局实例
4. 所有通过 `get_knowledge_rag()` 的调用改为通过 KnowledgeHub

**影响范围**: 需排查所有引用 `knowledge.py` 的代码。

### 3.2 KnowledgeHub (knowledge_hub/) → 保留并增强

**当前状态**: 架构合理（connector/processor 分层），已有 connector 基类和3种实现。

**需要修复的问题**:
1. `hub.py:add_source()` 中 `asyncio.get_event_loop().run_until_complete()` 在异步环境会报错 → 改为 `async` 方法
2. `hub.py:remove_source()` 同样的异步问题 → 改为 `async` 方法
3. 部分 connector 缺少错误处理和重连机制

**增强方向**:
1. `LocalConnector` 增加文件变更检测（基于 mtime）支持增量同步
2. `DatabaseConnector` 增加连接池和超时配置
3. `WebSearchConnector` 增加结果缓存 TTL
4. 扩展 connector 接口，增加 `health_check()` 方法

### 3.3 GraphRAG (graph_rag/) → 下沉为基础能力

**当前状态**: 已有 `GraphProcessor` 作为 KnowledgeHub 的 processor。架构正确。

**处理**:
1. 保持 `graph_rag/` 作为独立模块（Layer 1）
2. KnowledgeHub 的 `GraphProcessor` 作为调用入口
3. 确保初始化顺序正确（GraphRAG 可选，LightRAG 未安装时优雅降级）

### 3.4 VectorStore (agent/vector_store.py) → 下沉为基础能力

**当前状态**: 已被 KnowledgeHub 和 KnowledgeRAG 共用。

**处理**:
1. 删除 KnowledgeRAG 引用后，仅保留 KnowledgeHub 和 GraphRAG 对其的引用
2. 考虑移至 `backend/modules/infrastructure/` 目录（与 Memory 同级）

### 3.5 ExperienceEngine (agent/experience.py) → 重构

**当前状态**: 空壳实现，`_analyze_and_generate_skill()` 用字符串截取而非 LLM。

**重构方向**:
1. 用 LLM 驱动的分析替代字符串截取
2. 引入轨迹系统作为输入源
3. 新技能进入 candidates 目录，需人工审核
4. 与 TraceStore 紧密集成

---

## 四、SuperWorkers Plugin 详细设计

### 4.1 插件结构

```
backend/modules/plugins/superworkers/
├── __init__.py              # 导出 Plugin 和 __plugin__
├── plugin.py                # SuperWorkersPlugin 主类
├── using_superworkers.py    # 入口技能 - 让 Agent 发现 SuperWorkers
├── task_knowledge_review.py # 核心工作流 - 任务前知识审查
├── execution_standards.py   # 执行过程规范
├── trace_recording.py       # 轨迹记录 Hook (自动)
├── trace_analyzer.py        # 分析近期轨迹 (人工触发)
├── skill_distiller.py       # 从轨迹提炼技能 (人工触发)
└── skill_refiner.py         # 优化已有技能 (人工触发)
```

### 4.2 SuperWorkersPlugin 主类

遵循 Superpowers 的模式，继承 `Plugin` 基类：

```python
class SuperWorkersPlugin(Plugin):
    name = "superworkers"
    version = "1.0.0"
    description = "企业工作流：知识检索、技能匹配、轨迹记录、经验进化"
    author = "AIE Team"
    enabled_by_default = False  # 默认关闭，可手动开启
```

与 Superpowers 一致的模式：
- `on_load()`: 延迟导入并初始化所有技能
- `get_hooks()`: 聚合所有技能的 Hook（trace_recording 的自动 Hook）
- `get_tools()`: 聚合所有技能提供的工具（如需要）
- `_create_plugin()` 工厂函数导出 `__plugin__`

### 4.3 入口技能: using-superworkers

**定位**: 类似 superpowers 的 `using-superpowers`，作为 Agent 发现 SuperWorkers 的入口。

**关键设计**:
- **不是 always: true** - 通过 AIE 系统提示词中的引导让 Agent 发现
- `should_activate(message)`: 当消息涉及企业任务、专业知识需求、办公场景时返回 true
- 激活后告知 Agent 可用的 SuperWorkers 技能列表和用法
- 指向核心工作流技能 `task-knowledge-review`

**系统提示词引导**（在 context.py 的 identity 部分添加）:
```
在企业办公场景中，你应该优先使用 SuperWorkers 工作体系来获取知识和指导。
当你面临以下情况时，考虑使用 SuperWorkers：
- 需要查询企业内部知识或文档
- 需要使用已有的技能来完成工作
- 面对企业内部的专业任务
- 需要参考之前的工作经验
使用 read_file(path='backend/modules/plugins/superworkers/using_superworkers.py') 来激活 SuperWorkers。
```

### 4.4 核心工作流: task-knowledge-review

**这是 SuperWorkers 最关键的技能**，指导 Agent 在执行企业任务前完成知识准备：

```
收到企业任务后的工作流程：

1. 任务分析
   - 理解任务目标、类型、涉及的领域
   - 判断是否需要专业知识支持

2. 本地技能检查 (priority: highest)
   - 检查本地 skills 目录是否有匹配的技能
   - 匹配条件: 技能描述与任务相关 + 依赖满足
   - 有匹配 → 加载技能内容，参考执行
   - 无匹配 → 进入下一步

3. 企业知识检索 (priority: high)
   - 通过 KnowledgeHub 检索相关企业知识
   - 检索策略: 先用 hybrid 模式，结果不足时补充 graph 模式
   - 找到相关知识 → 整理成参考材料，在执行中引用
   - 未找到 → 记录"知识缺失"，执行后建议补充

4. 网络搜索补充 (priority: low)
   - 仅当本地技能和企业知识都不足时
   - 使用 WebSearch 工具搜索公开信息

5. 整理参考资料
   - 将检索到的技能和知识整理成结构化参考
   - 标注来源，便于追溯
   - 评估知识相关性和可信度

6. 执行任务
   - 基于参考资料执行任务
   - 如果发现参考资料不够，可以再次检索
   - 全程记录操作轨迹（自动 Hook 完成）
```

**实现方式**: 这是一个**指导性**技能，不是代码逻辑。Agent 读取此技能后，自行按照流程决策。技能中会列出可用的工具和调用方式。

### 4.5 执行过程规范: execution-standards

指导 Agent 在执行过程中遵循的规范：
- 知识引用规范：使用企业知识时标注来源
- 错误处理规范：遇到知识不足时如何处理
- 结果验证规范：如何验证执行结果是否正确
- 轨迹记录配合：告知 Agent 轨迹在自动记录，无需手动记录

### 4.6 轨迹记录: trace-recording (自动 Hook)

**核心 Hook 实现** - 通过 Plugin 的 Hook 机制自动运行：

```python
class TraceRecordingSkill:
    """轨迹记录 - 通过 Hook 自动运行，无需人工触发"""

    def get_hooks(self) -> list[Hook]:
        return [
            Hook(event="before_process", callback=self._on_before_process,
                 description="轨迹记录启动", priority=10),
            Hook(event="tool_called", callback=self._on_tool_called,
                 description="工具调用记录", priority=0),
            Hook(event="tool_result", callback=self._on_tool_result,
                 description="工具结果记录", priority=0),
            Hook(event="after_process", callback=self._on_after_process,
                 description="轨迹完成与保存", priority=10),
        ]
```

### 4.7 进化技能 (人工触发)

三个技能均不是自动运行的，需要用户通过对话触发：

| 技能 | 触发方式 | 功能 |
|------|----------|------|
| `trace-analyzer` | "分析一下最近的轨迹" / "看看最近做得怎么样" | 汇总近期轨迹，分析成功率、常见问题、知识使用情况 |
| `skill-distiller` | "把这个经验整理成技能" / "总结一下最佳实践" | 从成功轨迹中提炼 candidate skill |
| `skill-refiner` | "优化一下xxx技能" / "不要这样做" | 根据用户反馈修改已有技能 |

**candidate skill 审核流程**:
```
trace-analyzer 分析轨迹
    ↓
skill-distiller 生成 candidate
    ↓ 存入 workspace/skills/_candidates/
skill-refiner 或人工审核
    ↓ 用户确认发布
移动到 workspace/skills/
    ↓
进入正常技能池
```

---

## 五、轨迹系统设计

### 5.1 轨迹记录内容

全量记录 Agent 的工作过程，每条轨迹包含：

```json
{
  "trace_id": "uuid",
  "session_id": "session-uuid",
  "started_at": "2026-03-29T10:00:00",
  "ended_at": "2026-03-29T10:05:30",

  "input": {
    "user_message": "帮我查一下Q1的销售数据",
    "detected_intent": "data_query",
    "channel": "web"
  },

  "knowledge_stage": {
    "local_skills_checked": ["sales-report"],
    "local_skills_used": ["sales-report"],
    "enterprise_knowledge_queried": true,
    "knowledge_results": [
      {"source": "knowledge_hub:wiki:sales-process", "summary": "...", "relevance": 0.8},
      {"source": "graph_rag", "entities": ["销售部门", "Q1"], "relevance": 0.6}
    ],
    "knowledge_helpful": true
  },

  "execution": {
    "iterations": [
      {
        "iteration": 1,
        "llm_reasoning": "用户需要查询Q1销售数据...",
        "tool_calls": [
          {
            "tool": "knowledge_retrieve",
            "arguments": {"query": "Q1销售数据", "mode": "hybrid"},
            "result_summary": "找到3条相关知识...",
            "success": true,
            "duration_ms": 850
          },
          {
            "tool": "query_database",
            "arguments": {"question": "查询2026年Q1销售总额"},
            "result_summary": "Q1销售总额: 1,234,567元",
            "success": true,
            "duration_ms": 1200
          }
        ],
        "response_preview": "根据查询结果，2026年Q1的销售总额为..."
      }
    ],
    "total_iterations": 3,
    "total_tool_calls": 5,
    "total_duration_ms": 8500
  },

  "output": {
    "final_response_preview": "2026年Q1销售报告...",
    "outcome": "success",
    "user_feedback": null
  },

  "metadata": {
    "model": "deepseek-chat",
    "plugin_active": "superworkers",
    "trace_file": "traces/2026-03/29/trace_xxx.jsonl"
  }
}
```

### 5.2 存储结构

```
data/
└── traces/
    ├── index.db              # SQLite 元数据索引（快速查询）
    ├── 2026-03/              # 按月分目录
    │   ├── 29/
    │   │   ├── trace_001.jsonl
    │   │   ├── trace_002.jsonl
    │   │   └── ...
    │   └── ...
    └── ...
```

**index.db 表结构**:
```sql
CREATE TABLE traces (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    task_type TEXT,           -- 分类：data_query / doc_writing / analysis / ...
    outcome TEXT,             -- success / failure / partial
    has_knowledge BOOLEAN,    -- 是否使用了知识检索
    knowledge_helpful BOOLEAN,-- 知识是否有帮助
    tool_calls_count INTEGER,
    total_duration_ms INTEGER,
    user_feedback TEXT,
    trace_file TEXT           -- JSONL 文件路径
);

CREATE INDEX idx_traces_date ON traces(started_at);
CREATE INDEX idx_traces_type ON traces(task_type);
CREATE INDEX idx_traces_outcome ON traces(outcome);
```

### 5.3 日志空间管理

**设计原则**:
- 本地默认保留 30 天（可配置）
- 不做"温数据"压缩（session 中已保存对话日志）
- 可选配置远端日志存储系统
- 过期日志自动推送到远端后删除本地

**配置**:
```yaml
# config/plugins/superworkers.yaml
options:
  trace:
    enabled: true
    local_retain_days: 30          # 本地保留天数，默认30
    remote_storage: null            # 远端存储配置（可选）
      # type: "s3" | "oss" | "api"
      # endpoint: "https://..."
      # bucket: "aie-traces"
      # credentials: {...}
    auto_cleanup: true              # 自动清理过期日志
    cleanup_interval_hours: 24      # 清理检查间隔
```

**清理流程**:
```
定时任务 (cleanup_interval_hours)
    → 扫描 traces/ 目录
    → 找出超过 local_retain_days 的日志
    → 如果配置了 remote_storage:
        → 推送到远端
        → 推送成功后删除本地文件
        → 更新 index.db
    → 如果未配置 remote_storage:
        → 直接删除
        → 更新 index.db
```

---

## 六、ExperienceEngine 重构设计

### 6.1 新架构

```
┌─────────────────────────────────────────┐
│           ExperienceEngine (重构)        │
│                                         │
│  输入:                                   │
│  ├── TraceStore (全量轨迹)              │
│  ├── 用户对话反馈                        │
│  └── 人工触发指令                        │
│                                         │
│  处理:                                   │
│  ├── trace_analyzer (LLM驱动分析)       │
│  ├── skill_distiller (LLM驱动提炼)      │
│  └── skill_refiner (LLM驱动优化)        │
│                                         │
│  输出:                                   │
│  ├── CandidateSkill (待审核技能)        │
│  ├── SkillAnalysisReport (分析报告)     │
│  └── SkillUpdate (技能修改建议)          │
│                                         │
│  存储:                                   │
│  ├── workspace/skills/_candidates/      │
│  └── memory/experience/                 │
└─────────────────────────────────────────┘
```

### 6.2 与旧系统的关系

| 旧组件 | 处理 | 新位置 |
|--------|------|--------|
| `WorkFeedback` | 保留并增强 | TraceStore 中的 outcome + user_feedback |
| `LearnedSkill` | 保留数据结构 | 演变为 CandidateSkill |
| `ExperienceEngine._analyze_and_generate_skill()` | 完全重写 | LLM 驱动分析 |
| `feedback_store/` | 废弃 | 由 TraceStore 替代 |
| `skills_store/` | 保留 | 作为 learned skills 的持久化 |

### 6.3 Candidate Skill 管理

```
workspace/skills/
├── _candidates/               # 待审核技能（不入 skills 注册）
│   ├── 2026-03-29-sales-query-practice/
│   │   └── SKILL.md
│   └── 2026-03-29-error-handling/
│       └── SKILL.md
├── morning_briefing/          # 正式技能
│   └── SKILL.md
└── ...
```

- `_candidates/` 目录以日期前缀命名，方便排序和追溯
- SkillsLoader 在扫描时**跳过** `_candidates/` 目录
- 用户审核通过后，将技能移出 `_candidates/` 到正式目录

---

## 七、与现有系统的集成点

### 7.1 系统提示词 (context.py)

在 `_get_identity()` 中添加 SuperWorkers 发现引导（一小段文字），不改变现有结构。

### 7.2 Agent Loop (loop.py)

当前 loop 已有 `tool_called` 和 tool result 的处理逻辑。SuperWorkers 通过 Hook 机制监听这些事件，**不需要修改 loop.py 的核心代码**。

但需要确认：当前 PluginManager 的 `emit_event()` 是否在 loop 中被调用？需要检查 `app.py` 中的初始化和事件发射逻辑。

### 7.3 KnowledgeHub API

现有 API (`/api/knowledge_hub/`) 保持不变。SuperWorkers 的技能指导 Agent 通过已有的工具调用这些 API，不需要新增 API。

### 7.4 Plugin 配置

```yaml
# config/plugins.yaml 中添加
plugins:
  superworkers:
    enabled: true
    options:
      workflow:
        local_skill_check: true
        enterprise_search: true
        web_search_fallback: true

      knowledge_priority:
        - local_skills
        - knowledge_hub
        - graph_rag
        - web_search

      trace:
        enabled: true
        local_retain_days: 30
        remote_storage: null
        auto_cleanup: true
        cleanup_interval_hours: 24

      evolution:
        min_traces_for_distill: 5
        require_human_review: true
```

---

## 八、实施阶段规划

### Phase 1: 基础整合 (优先)

**目标**: 清理现有代码，建立干净的架构基础

1. 废弃 KnowledgeRAG，清理所有引用
2. 修复 KnowledgeHub 的异步 bug
3. 确认 GraphRAG 作为 Layer 1 基础能力的正确集成
4. 创建 SuperWorkers Plugin 骨架（plugin.py + __init__.py）
5. 实现 `using-superworkers` 入口技能
6. 在系统提示词中添加 SuperWorkers 发现引导

### Phase 2: 核心工作流

**目标**: Agent 能主动利用知识执行任务

1. 实现 `task-knowledge-review` 核心技能
2. 实现 `execution-standards` 执行规范
3. 确保 Agent 能正确调用 KnowledgeHub 检索
4. 端到端测试：Agent 接到企业任务 → 查知识 → 执行

### Phase 3: 轨迹系统

**目标**: 完整记录 Agent 工作过程

1. 实现 `trace-recording` Hook
2. 实现 TraceStore（JSONL 文件 + SQLite 索引）
3. 在 Agent Loop 中接入事件发射（如果尚未接入）
4. 实现日志清理机制

### Phase 4: 经验进化

**目标**: 从轨迹中提炼和优化技能

1. 重构 ExperienceEngine，引入 LLM 驱动分析
2. 实现 `trace-analyzer` 技能
3. 实现 `skill-distiller` 技能
4. 实现 `skill-refiner` 技能
5. 实现 candidate skill 管理流程

### Phase 5: 增强扩展 (后续)

- KnowledgeHub Connector 扩展（飞书、钉钉、Confluence）
- 远端日志存储集成
- 企业技能共享平台（Server 端 ClawdHub）
- 知识使用效果分析和检索优化

---

## 九、关键设计决策记录

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 知识注入方式 | 通过 using-superworkers 入口技能引导发现 | 保持 AIE 通用性，不强制 always:true |
| 三个知识系统处理 | 废弃 KnowledgeRAG，KnowledgeHub 保留增强，GraphRAG 下沉基础层 | 消除冗余，架构清晰 |
| 轨迹记录粒度 | 全量记录（方案C） | 最大化后续可利用数据 |
| 日志保留策略 | 本地30天 + 可选远端推送，不做温数据压缩 | session 已存对话日志，简化管理 |
| SuperWorkers 技能性质 | 指导性规则，非模板化 | 企业场景多变，Agent 需要自主决策 |
| 技能进化触发 | 人工触发 + 人工审核 | 谨慎进化，避免扰动稳定技能 |
| KnowledgeHub 定位 | 企业知识源聚合入口 | 统一管理，可配置可扩展 |
