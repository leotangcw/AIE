# AIE (AI Employee) 项目设计与开发计划

**版本**: v1.0
**日期**: 2026-03-02
**基于**: CountBot + OpenClaw 参考设计

---

## 一、项目愿景

打造一个适合中国企业使用的 AI 员工系统，通过渐进式替代、经验资产化、规则内嵌化，实现对企业工作流程、经验和知识的自动化承载与优化。

---

## 二、核心需求汇总

### 2.1 功能模块优先级

| 优先级 | 模块 | 描述 |
|--------|------|------|
| P0 | 本地模型配置 | 支持 LLM/TTS/ASR/文生图等，可配置本地部署 |
| P0 | 经验学习系统 | 自动学习、积累 Skills，支持跨 AIE 交换 |
| P1 | 企业规则集成 | 规章制度自动化应用，新 AIE 快速初始化 |
| P1 | 数据安全 | 分级权限控制，可选功能 |
| P1 | 知识库集成 | RAG 能力，多源知识库挂接 |
| P2 | 通信平台 | 微信/钉钉/飞书/WeLink 集成 |
| P2 | 高级 Agent | 多 Agent 协作、Team 模式 |

### 2.2 技术约束

- **开发环境隔离**: 独立工作目录、独立配置、独立端口
- **端口规划**:
  - Gateway: 20000
  - Server API: 21000
  - Web UI: 22000
- **运行环境隔离**: 与现有 bot 不冲突

---

## 三、架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        AIE Enterprise                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     AIE Server (可选)                        ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          ││
│  │  │ Skills Exchange │ │ Rules Store │ │ AIE Registry │        ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ 同步 (可选)
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                      AIE Client (Per Employee)                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      AIE Gateway                             ││
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       ││
│  │  │  Agent  │  │ Memory  │  │ Skills  │  │  Rules  │       ││
│  │  │  Core   │  │ System  │  │ Engine  │  │ Engine  │       ││
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       ││
│  └───────┼────────────┼────────────┼────────────┼─────────────┘│
│          │            │            │            │               │
│  ┌───────▼────────────▼────────────▼────────────▼───────┐     │
│  │                    Tools & Providers                    │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            │     │
│  │  │  Local   │  │   RAG    │  │ Channel  │            │     │
│  │  │  Model   │  │ Knowledge│  │ Adapter  │            │     │
│  │  └──────────┘  └──────────┘  └──────────┘            │     │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### 3.2 模块设计

#### 3.2.1 本地模型配置层 (Model Provider)

```python
# 核心设计
class ModelProvider(ABC):
    @abstractmethod
    def chat(self, messages: list, **kwargs) -> ChatResponse:
        pass

    @abstractmethod
    def embeddings(self, texts: list) -> list:
        pass

# 支持的类型
- LocalLLM: 本地 LLM (Ollama, vLLM, LLaMA.cpp, ChatGLM 等)
- LocalTTS: 本地 TTS
- LocalASR: 本地 ASR
- LocalDiffusion: 本地文生图
- CloudProvider: 云端模型 (OpenAI, Anthropic 等，作为 fallback)
```

#### 3.2.2 经验学习系统 (Skills Engine)

```python
# 核心设计
class SkillsEngine:
    def learn(self, feedback: WorkFeedback) -> Skill:
        """从反馈中学习经验"""

    def exchange(self, skill: Skill) -> list:
        """从 Server 获取/交换技能"""

    def apply(self, context: WorkContext) -> AppliedSkill:
        """应用技能到工作上下文"""

# Skill 格式: Markdown/YAML
# 存储位置: local + remote (Server)
```

#### 3.2.3 规则引擎 (Rules Engine)

```python
# 核心设计
class RulesEngine:
    def load_rules(self, source: RuleSource) -> list:
        """从文档加载规则"""

    def evaluate(self, action: Action, context: Context) -> RuleResult:
        """评估动作是否符合规则"""

    def init_new_aie(self, template: Aietemplate) -> InitialState:
        """新 AIE 初始化"""
```

#### 3.2.4 数据安全层 (Security)

```python
# 核心设计
class SecurityEngine:
    def classify(self, data: Data) -> SecurityLevel:
        """数据分类"""

    def check_access(self, aie: AIE, data: Data) -> bool:
        """权限检查"""

    # 可选功能，未启用时正常工作
```

#### 3.2.5 知识库 RAG

```python
# 核心设计
class KnowledgeRAG:
    def connect(self, source: KnowledgeSource) -> Connection:
        """连接知识源"""

    def retrieve(self, query: str, top_k: int) -> list:
        """检索相关知识"""

    def augment(self, context: Context, knowledge: list) -> AugmentedContext:
        """增强上下文"""
```

---

## 四、开发阶段规划

### Phase 1: 基础框架搭建 (2-3 周)

**目标**: 基于 CountBot 搭建可运行的基础框架

| 任务 | 描述 | 预估 |
|------|------|------|
| 1.1 | 项目初始化，创建独立目录结构 | 1 天 |
| 1.2 | 配置环境隔离 (端口、配置目录) | 1 天 |
| 1.3 | 迁移 CountBot 核心代码 | 3 天 |
| 1.4 | 基础 Agent Loop 测试 | 2 天 |
| 1.5 | 基础 Web UI 适配 | 2 天 |
| 1.6 | 本地运行验证 | 1 天 |

**交付物**: 可运行的 AIE 基础客户端

---

### Phase 2: 本地模型支持 (2 周)

**目标**: 支持本地模型配置

| 任务 | 描述 | 预估 |
|------|------|------|
| 2.1 | 设计 Model Provider 抽象层 | 2 天 |
| 2.2 | 实现 LocalLLM Provider (Ollama/vLLM) | 3 天 |
| 2.3 | 实现 TTS/ASR Provider 接口 | 2 天 |
| 2.4 | 实现文生图 Provider 接口 | 2 天 |
| 2.5 | 配置界面适配 | 2 天 |
| 2.6 | 测试验证 | 1 天 |

**交付物**: 可配置本地模型的 AIE

---

### Phase 3: 经验学习系统 (3 周)

**目标**: Skills 自动学习与积累

| 任务 | 描述 | 预估 |
|------|------|------|
| 3.1 | Skills 数据结构设计 | 2 天 |
| 3.2 | 反馈收集机制 | 2 天 |
| 3.3 | 自动经验总结模块 | 3 天 |
| 3.4 | Skills 存储与检索 | 2 天 |
| 3.5 | Skills 应用引擎 | 3 天 |
| 3.6 | 本地测试验证 | 2 天 |

**交付物**: 具有经验学习能力的 AIE

---

### Phase 4: 企业规则系统 (2 周)

**目标**: 企业规则自动应用

| 任务 | 描述 | 预估 |
|------|------|------|
| 4.1 | 规则格式定义 (Markdown/YAML) | 1 天 |
| 4.2 | 规则加载器 | 2 天 |
| 4.3 | 规则评估引擎 | 3 天 |
| 4.4 | 新 AIE 初始化模板 | 2 天 |
| 4.5 | 规则配置界面 | 2 天 |
| 4.6 | 测试验证 | 1 天 |

**交付物**: 支持企业规则集成的 AIE

---

### Phase 5: 数据安全层 (2 周)

**目标**: 可选的分级权限控制

| 任务 | 描述 | 预估 |
|------|------|------|
| 5.1 | 安全级别定义 | 1 天 |
| 5.2 | 数据分类接口 | 2 天 |
| 5.3 | 权限检查引擎 | 3 天 |
| 5.4 | AIE 级别继承机制 | 2 天 |
| 5.5 | 界面配置 | 2 天 |
| 5.6 | 测试验证 | 1 天 |

**交付物**: 可选的数据安全功能

---

### Phase 6: 知识库 RAG (3 周)

**目标**: 企业知识库集成

| 任务 | 描述 | 预估 |
|------|------|------|
| 6.1 | 知识源抽象层 | 2 天 |
| 6.2 | 文档加载器 (PDF/Word/Markdown) | 2 天 |
| 6.3 | 向量存储 (本地) | 2 天 |
| 6.4 | 检索增强生成 | 3 天 |
| 6.5 | 知识库管理界面 | 3 天 |
| 6.6 | 测试验证 | 1 天 |

**交付物**: 支持 RAG 的 AIE

---

### Phase 7: 通信平台集成 (3 周)

**目标**: 微信/钉钉/飞书/WeLink

| 任务 | 描述 | 预估 |
|------|------|------|
| 7.1 | 通道抽象层重构 | 2 天 |
| 7.2 | 飞书适配器 | 3 天 |
| 7.3 | 钉钉适配器 | 3 天 |
| 7.4 | 企业微信适配器 | 3 天 |
| 7.5 | 微信适配器 (可选) | 2 天 |
| 7.6 | 测试验证 | 2 天 |

**交付物**: 多平台支持的 AIE

---

### Phase 8: 高级 Agent 能力 (持续迭代)

**目标**: 多 Agent 协作、Team 模式

| 任务 | 描述 | 预估 |
|------|------|------|
| 8.1 | 多 Agent 架构设计 | 2 周 |
| 8.2 | Agent Team 协作 | 2 周 |
| 8.3 | 记忆系统优化 | 2 周 |
| 8.4 | 持续迭代 | - |

---

## 五、技术选型

### 5.1 技术栈

| 层级 | 技术 |
|------|------|
| 后端语言 | Python 3.11+ |
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | SQLite (开发) / PostgreSQL (生产) |
| ORM | SQLAlchemy |
| 向量存储 | Chroma / FAISS (本地) |
| 前端 | Vue 3 + TypeScript + Vite |
| 实时通信 | WebSocket |

### 5.2 本地模型支持

| 类型 | 支持方案 |
|------|----------|
| LLM | Ollama, vLLM, LLaMA.cpp, ChatGLM, LocalAI |
| TTS | Coqui TTS, Edge TTS (可本地部署) |
| ASR | Whisper (本地), FunASR |
| 文生图 | Stable Diffusion API, ComfyUI |

---

## 六、接口预留

### 6.1 Server 端接口 (Phase 1 预留)

```yaml
# AIE Server API (未来实现)
paths:
  /api/skills/exchange:
    post: 技能交换
  /api/skills/publish:
    post: 发布技能
  /api/rules/sync:
    post: 规则同步
  /api/aie/register:
    post: AIE 注册
  /api/aie/heartbeat:
    post: 心跳
```

### 6.2 离线工作模式

- Server 不可用时，自动降级为独立工作模式
- 本地 Skills 和 Rules 正常可用
- 记录待同步内容，待恢复后自动同步

---

## 七、开发里程碑

| 里程碑 | 预计时间 | 交付物 |
|--------|----------|--------|
| M1 | 第 1 个月末 | 可运行的 AIE 基础客户端 |
| M2 | 第 2 个月末 | 支持本地模型的 AIE |
| M3 | 第 3 个月末 | 具备经验学习能力 |
| M4 | 第 4 个月末 | 完整的 MVP 产品 |

---

## 八、风险与应对

| 风险 | 应对措施 |
|------|----------|
| CountBot 代码改造量大 | 渐进式改造，保持可运行 |
| 本地模型兼容性 | 抽象层设计，支持多种适配器 |
| 经验学习效果 | 人工审核 + 反馈机制 |
| 性能瓶颈 | 异步处理 + 缓存 |

---

## 九、后续优化方向

- 记忆系统增强 (长期记忆 + 短期记忆)
- Agent Team 协作模式
- 语音交互 (TTS/ASR)
- 可视化工作区
- 移动端支持

---

**文档状态**: 等待批准后启动开发
