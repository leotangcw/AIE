# 技能系统设计

**版本**: v1.0
**更新日期**: 2026-03-08
**文件路径**: `backend/modules/agent/skills.py`

---

## 1. 模块概述

技能系统是 AIE 的可插拔插件系统，支持内置技能和自定义技能的热加载、启用/禁用管理。

### 核心功能
- 技能文件加载（`SKILL.md`）
- 技能启用/禁用管理
- 系统提示词注入
- 按需加载

---

## 2. 技能结构

### 目录结构

```
skills/
└── my-skill/
    ├── SKILL.md           # 技能定义文件（必需）
    └── scripts/           # 辅助脚本（可选）
        └── helper.py
```

### SKILL.md 格式

```markdown
---
name: baidu-search
description: 百度 AI 搜索。支持网页搜索、百度百科、秒懂百科、AI 智能生成四种模式。
version: 1.0.0
always: false
requirements:
  - requests
---

# 百度 AI 搜索

## 使用说明
当用户需要搜索信息时，使用此技能...

## 工具调用
使用 exec 工具执行 scripts/search.py...
```

### Frontmatter 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | string | ✅ | — | 技能显示名称 |
| `description` | string | ✅ | — | 技能描述 |
| `version` | string | ❌ | `"1.0.0"` | 版本号 |
| `author` | string | ❌ | `""` | 作者 |
| `always` | boolean | ❌ | `false` | 是否自动加载到系统提示词 |
| `requirements` | list[str] | ❌ | `[]` | Python 依赖包列表 |

---

## 3. 核心组件

### 3.1 Skill

**文件**: `backend/modules/agent/skills.py`

#### 职责
- 封装技能元数据和内容

```python
skill = Skill(
    name="baidu-search",
    path=Path("skills/baidu-search"),
    content="SKILL.md 完整内容",
)
```

#### 方法

| 方法 | 说明 |
|------|------|
| `get_summary()` | 返回技能摘要 |
| `check_requirements()` | 检查依赖是否已安装 |
| `get_missing_requirements()` | 返回缺失的依赖列表 |

### 3.2 SkillsLoader

**文件**: `backend/modules/agent/skills.py`

#### 职责
- 技能发现、加载、启用/禁用

#### 核心方法

```python
class SkillsLoader:
    def __init__(self, skills_dir: Path):
        """初始化技能加载器"""

    def list_skills() -> list[Skill]:
        """列出所有技能"""

    def load_skill(name: str) -> Skill:
        """加载技能完整内容"""

    def toggle_skill(name: str, enabled: bool):
        """启用/禁用技能"""

    def get_always_skills() -> list[str]:
        """获取自动加载的技能列表"""

    def build_skills_summary() -> str:
        """构建技能摘要（用于系统提示词）"""

    def load_skills_for_context(names: list[str]) -> str:
        """加载指定技能内容"""

    def add_skill(name: str, content: str):
        """创建新技能"""

    def update_skill(name: str, content: str):
        """更新技能内容"""

    def delete_skill(name: str):
        """删除技能"""

    def reload():
        """重新扫描技能目录"""

    def get_stats() -> dict:
        """获取统计信息"""
```

---

## 4. 技能加载机制

### 启动时加载

```
SkillsLoader.__init__()
  │
  ├─ _load_disabled_skills()
  │   └─ 读取 .skills_config.json → disabled set
  │
  └─ _load_all_skills()
      └─ 遍历 skills/ 目录
          ├─ 读取 SKILL.md
          ├─ 解析 frontmatter
          └─ 创建 Skill 对象 → _skills dict
```

### 系统提示词注入

```
ContextBuilder.build_system_prompt()
  │
  ├─ get_always_skills()
  │   └─ 返回 always=true 且已启用的技能名列表
  │
  ├─ load_skills_for_context(always_skills)
  │   └─ 拼接技能完整内容
  │
  └─ build_skills_summary()
      └─ 返回所有已启用技能的摘要列表
```

### 按需加载

非 `always` 技能不会注入系统提示词，而是在摘要中列出。Agent 需要时通过 `read_file` 工具读取：

```
Agent: read_file("skills/baidu-search/SKILL.md")
→ ReadFileTool 检测到技能路径
→ 通过 SkillsLoader.load_skill() 加载
→ 返回完整技能内容
```

---

## 5. 内置技能

| 技能 | 说明 | always |
|------|------|--------|
| `baidu-search` | 百度 AI 搜索 | false |
| `cron-manager` | 定时任务管理 | false |
| `email` | 通过 QQ 或 163 邮箱发送邮件 | false |
| `image-analysis` | 图片分析与识别 | false |
| `image-gen` | AI 图片生成 | false |
| `map` | 高德地图路线规划与 POI 搜索 | false |
| `news` | 新闻与资讯查询 | false |
| `weather` | 天气查询与预报 | false |
| `web-design` | 网页设计与部署 | false |
| `agent-browser` | 浏览器自动化 CLI | false |

---

## 6. API 接口

**文件**: `backend/api/skills.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/skills` | GET | 列出所有技能 |
| `/api/skills` | POST | 创建新技能 |
| `/api/skills/{name}` | GET | 获取技能详情 |
| `/api/skills/{name}` | PUT | 更新技能 |
| `/api/skills/{name}` | DELETE | 删除技能 |
| `/api/skills/{name}/toggle` | POST | 启用/禁用技能 |

---

## 7. 配置管理

### .skills_config.json

技能启用/禁用状态存储在工作空间根目录的 `.skills_config.json`：

```json
{
  "disabled": ["skill-x", "skill-y"]
}
```

- 不在 `disabled` 列表中的技能默认启用
- 此文件由 `SkillsLoader` 自动管理
- 可手动编辑

---

## 8. 自定义技能开发

### 步骤

1. 在 `skills/` 目录创建技能文件夹：

```bash
mkdir skills/my-skill
```

2. 创建 `SKILL.md`：

```markdown
---
name: 我的技能
description: 技能描述
version: 1.0.0
always: false
---

# 我的技能

## 使用说明
当用户需要 XXX 时，按以下步骤操作...
```

3. （可选）添加辅助脚本：

```bash
mkdir skills/my-skill/scripts
```

4. 通过 Web UI 或 API 启用技能

---

## 9. 前端集成

### Store

```typescript
const skillsStore = useSkillsStore()

// 加载技能列表
await skillsStore.loadSkills()

// 启用/禁用技能
await skillsStore.toggleSkill(skillName, enabled)

// 创建技能
await skillsStore.createSkill({ name, content })
```

---

## 10. 待办事项 (TODO)

### 高优先级
- [ ] 添加更多内置技能
- [ ] 优化技能依赖安装

### 中优先级
- [ ] 技能市场/分享平台
- [ ] 技能版本管理

### 低优先级
- [ ] 技能组合/工作流
- [ ] 技能性能监控
