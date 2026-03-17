# 企业知识中枢 (KnowledgeHub) 模块设计文档

**创建日期**: 2026-03-17
**版本**: 1.0
**状态**: 已批准

---

## 一、模块概述

### 1.1 核心定位

**企业知识中枢 (KnowledgeHub)** 是企业Bot的可插拔独立插件模块，专注于企业内部知识的自动化检索、获取、处理、整合与输出。

- **定位**: 企业Bot的"知识供给中枢"
- **特点**: 独立运行、可灵活插拔、接口标准化
- **目标**: 替代传统RAG的简单召回拼接模式，采用智能化处理方式

### 1.2 与现有代码关系

基于现有的 `knowledge.py` (KnowledgeRAG) 进行重构和扩展，形成独立的可插拔模块。

---

## 二、整体架构

### 2.1 分层架构 (5层)

```
┌─────────────────────────────────────────────────────────────────┐
│                     知识模块 (KnowledgeHub)                     │
├─────────────────────────────────────────────────────────────────┤
│  1. 接口交互层    - API接口、配置管理、缓存刷新                    │
│  2. 知识接入层    - 本地文件、数据库、网页、企业软件                │
│  3. 知识处理层    - 直接检索、LLM加工、混合模式                   │
│  4. 缓存层        - 内存+本地文件缓存                            │
│  5. 存储层        - 向量存储、元数据存储                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 模块目录结构

```
knowledge_hub/
├── __init__.py           # 模块入口，导出主要类
├── config.py             # 配置模型
├── hub.py                # 核心类 KnowledgeHub
├── processors/           # 处理器
│   ├── __init__.py
│   ├── base.py          # 处理器基类
│   ├── direct.py        # 直接检索模式
│   ├── llm.py          # LLM加工模式
│   └── hybrid.py       # 混合模式
├── connectors/          # 知识接入器
│   ├── __init__.py
│   ├── base.py         # 接入器基类
│   ├── local.py        # 本地文件
│   ├── database.py     # 数据库(自动SQL)
│   ├── web.py          # 网页
│   └── feishu.py       # 飞书/企微
├── storage/             # 存储层
│   ├── __init__.py
│   ├── cache.py        # 简单缓存
│   └── vector.py       # 向量存储
└── skills/              # Skill池
    └── __init__.py
```

---

## 三、核心功能设计

### 3.1 处理模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **直接检索** | 快速返回原始检索结果 | 简单查询、需要原始知识 |
| **LLM加工** | 按提示词风格智能处理 | 需要精炼、整合知识 |
| **混合模式** | 多检索器融合+LLM优化 | 需要全面+精炼 |

### 3.2 LLM提示词风格

| 风格 | 名称 | 说明 |
|------|------|------|
| `compress` | 信息压缩 | 极致压缩，只提取关键重点 |
| `restate` | 关键复述 | 关键语义原文复述 |
| `rework` | 加工改写 | 知识加工增加模型自我理解 |

### 3.3 知识接入类型

| 类型 | 状态 | 说明 |
|------|------|------|
| 本地文件 | P0 | 支持Markdown等文本文件 |
| 数据库 | P1 | 自动SQL生成 |
| 网页 | P2 | 爬取解析 |
| 飞书/企微 | P2 | API对接 |

---

## 四、数据模型设计

### 4.1 配置模型

```python
class KnowledgeHubConfig:
    """模块配置"""
    # 模块开关
    enabled: bool = True

    # 处理模式配置
    default_mode: str = "direct"  # direct/llm/hybrid

    # LLM配置
    llm: LLMConfig = LLMConfig()

    # 缓存配置
    cache: CacheConfig = CacheConfig()

    # 知识源配置
    sources: list[SourceConfig] = []
```

### 4.2 LLM配置

```python
class LLMConfig:
    """LLM处理配置"""
    enabled: bool = False              # 总开关
    model: str = "gpt-3.5-turbo"      # 可配置切换
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    prompt_style: str = "compress"     # compress/restate/rework
    custom_prompts: dict = {}         # 用户自定义
```

### 4.3 缓存配置

```python
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    ttl: int = 3600                   # 秒
    max_memory_items: int = 100
```

---

## 五、接口设计

### 5.1 核心API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/knowledge_hub/retrieve` | POST | 知识检索 |
| `/api/knowledge_hub/query-db` | POST | 智能数据库查询 |
| `/api/knowledge_hub/config` | GET/PUT | 配置管理 |
| `/api/knowledge_hub/sources` | CRUD | 知识源管理 |
| `/api/knowledge_hub/cache/refresh` | POST | 刷新缓存 |

### 5.2 模块集成接口

```python
# 独立创建实例
hub = KnowledgeHub(config_path="config.json")
result = await hub.retrieve("问题")

# 集成到Agent
KnowledgeHubPlugin.integrate(agent)
agent.knowledge.retrieve("问题")
```

---

## 六、开发优先级

| 阶段 | 功能 | 优先级 |
|------|------|--------|
| 1 | 模块骨架 + 配置模型 | P0 |
| 2 | 直接检索模式 | P0 |
| 3 | 本地文件接入 | P0 |
| 4 | 简单缓存 | P0 |
| 5 | LLM加工模式 | P1 |
| 6 | 数据库自动SQL | P1 |
| 7 | 前端配置界面 | P1 |
| 8 | 网页接入 | P2 |

---

## 七、非功能需求

### 7.1 性能要求

- 普通检索响应: ≤1秒
- LLM加工响应: ≤5秒
- 缓存检索响应: ≤200ms

### 7.2 可扩展性

- 支持新增知识接入器
- 支持新增处理模式
- 支持模型切换

---

## 八、现有代码迁移

| 现有文件 | 迁移方式 |
|----------|----------|
| `backend/modules/agent/knowledge.py` | 重构为 `knowledge_hub/hub.py` |
| `backend/api/knowledge.py` | 扩展为 `knowledge_hub/api.py` |
| `frontend/.../KnowledgeConfig.vue` | 增强为 `knowledge/` 模块 |

---

**审批状态**: ✅ 已批准
**开始日期**: 2026-03-17
