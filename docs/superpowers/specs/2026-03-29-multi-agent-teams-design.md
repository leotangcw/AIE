# Multi-Agent Teams Integration Design (Delta Spec)

**Date**: 2026-03-29
**Scope**: Enhance AIE with CountBot v0.5.0 multi-agent orchestration + Teams split-panel UI

---

## 1. Existing Backend (Already Implemented — Do NOT Recreate)

The following backend components already exist and should be referenced, not rewritten:

### 1.1 AgentTeam Model (`backend/models/agent_team.py`)
- `id`: String(64), UUID primary key
- `name`: String(200)
- `description`: Text, nullable
- `mode`: "pipeline" | "graph" | "council"
- `agents`: JSON column (list of agent definition dicts)
- `is_active`, `cross_review`, `enable_skills`: Boolean
- `team_model_config`: Text (JSON string), nullable
- `use_custom_model`: Boolean
- `created_at`, `updated_at`: DateTime

### 1.2 Agent Teams API (`backend/api/agent_teams.py`)
Full CRUD already implemented:
- `GET /` — list all teams
- `POST /` — create team (with duplicate name check)
- `GET /{team_id}` — get team
- `PUT /{team_id}` — update team
- `DELETE /{team_id}` — delete team
- `POST /execute` — execute workflow via team
- `GET /{team_id}/config` — get team model config (merges with global)
- `PUT /{team_id}/config` — update team model config
- `DELETE /{team_id}/config` — reset to global defaults

Pydantic schemas: `AgentDefinition`, `AgentTeamCreate`, `AgentTeamUpdate`, `AgentTeamResponse`, `TeamModelConfigRequest`

### 1.3 WorkflowEngine (`backend/modules/agent/workflow.py`)
Already supports three modes: `run_pipeline()`, `run_graph()`, `run_council()`

### 1.4 Interrupt Handling (`backend/ws/events.py`)
`handle_interrupt_event()` already exists (lines ~402-479). Not in scope for this spec.

---

## 2. Backend Gaps — What Needs to Be Added/Modified

### 2.1 Add Missing Workflow Lifecycle Events to WorkflowEngine

**Problem**: WorkflowEngine emits `workflow_agent_start`, `workflow_agent_tool_call`, `workflow_agent_tool_result`, `workflow_agent_chunk`, `workflow_agent_complete` — but does NOT emit `workflow_start` or `workflow_complete`. The frontend needs these for Teams panel lifecycle.

**Changes to `backend/modules/agent/workflow.py`**:
- Emit `workflow_start` at the beginning of `run_pipeline()`, `run_graph()`, `run_council()`
  - Payload: `{type: "workflow_start", team_name, mode, agents: [{id, role, task}]}`
- Emit `workflow_complete` after final result assembly
  - Payload: `{type: "workflow_complete", team_name, mode, results_summary}`
- Emit `workflow_error` in exception handlers
  - Payload: `{type: "workflow_error", team_name, agent_id, error}`

### 2.2 Add `condition` Field to AgentDefinition Schema

**Problem**: Graph mode conditionals work via `workflow_run` tool (raw dicts) but the Teams CRUD API strips `condition` because `AgentDefinition` Pydantic schema doesn't include it.

**Change to `backend/api/agent_teams.py`**:
- Add `condition: Optional[str] = Field(None, description="Conditional expression (graph mode)")` to `AgentDefinition`

### 2.3 ContextBuilder Team Integration

**File**: `backend/modules/agent/context.py`

**2.3.1 Active Teams System Prompt Section**:
New method `_get_active_teams_section()`:
- Query DB for active teams (`is_active=True`)
- Format as system prompt section listing team name, mode, and member roles
- Called in `build_system_prompt()`

**2.3.2 Team Mention Detection**:
New method `_find_mentioned_team(user_message, active_teams)`:
- Scan for `@团队名` or `使用[团队名]` patterns
- Returns matched team or None

Modification to `build_messages()`:
- After building messages, check for team mention
- If found, prepend system reminder advising the agent to use `workflow_run` tool
- Advisory only — does not force execution

**2.3.3 Dynamic Config Updates**:
New methods for runtime config changes:
- `update_workspace(workspace: str)` — update workspace path
- `update_persona_config(config)` — update persona settings
- These make the context builder stateful where needed

### 2.4 WebSocket Task Notifications Enhancement

**File**: `backend/ws/task_notifications.py`

Add handlers for new workflow events:
- `workflow_start` → notify all connected sessions (or target session if session_id present)
- `workflow_agent_start` → per-agent start notification
- `workflow_agent_tool_call` → tool call tracking
- `workflow_agent_progress` → progress update
- `workflow_agent_complete` → per-agent completion
- `workflow_complete` → workflow completion
- `workflow_error` → error notification

Add new message types in `backend/ws/connection.py`:
- `WorkflowEventMessage` — generic workflow event wrapper
- `WorkflowStartMessage`, `WorkflowCompleteMessage`, `WorkflowErrorMessage` — specific types

---

## 3. Frontend Architecture

### 3.1 Layout Integration Point

Current ChatWindow structure:
```
<div class="main-container">
  <aside class="task-board-sidebar">  ← HeartbeatWidget + TaskBoard + TodoList
  <main class="main">                 ← Chat content (MessageList)
</div>
<footer class="input-area">           ← SubtaskProgress + input
<aside class="panel">                 ← activePanel overlay (sessions/memory/skills/etc)
```

**Modification**: Split `<main class="main">` into two panes when Teams is active:

```
<div class="main-container">
  <aside class="task-board-sidebar">  ← UNCHANGED
  <div class="chat-pane">             ← NEW wrapper (flex row)
    <main class="main">               ← Chat content (width: 55% default)
    <div class="teams-divider">       ← Draggable divider
    <div class="sub-agents-panel">    ← Sub-agent slots (width: 45% default)
  </div>
</div>
<footer class="input-area">           ← UNCHANGED
<aside class="panel">                 ← UNCHANGED (independent overlay)
```

Key: The `activePanel` overlay system is completely independent and unaffected. Both Teams panel and a config panel (memory, settings, etc.) can be visible simultaneously.

### 3.2 Teams Button in Toolbar

Add to ChatWindow header actions (after "技能", before "经验"):
- Icon: `Users` from lucide-vue-next
- Label: "Teams"
- Active state: highlighted + badge showing running sub-agent count
- Toggle behavior: click to open/close the sub-agent panel

### 3.3 teamsStore (Pinia)

**File**: `frontend/src/store/teams.ts`

```typescript
interface SubAgentState {
  agent_id: string
  role: string
  status: 'queued' | 'running' | 'waiting' | 'completed' | 'error'
  progress: number           // 0-100
  tool_count: number
  tool_name: string | null
  messages: Message[]         // Independent message stream for this agent
  duration: number            // seconds elapsed
  started_at: number | null
  completed_at: number | null
}

interface WorkflowState {
  is_active: boolean
  team_name: string
  mode: 'pipeline' | 'graph' | 'council'
  agents: SubAgentState[]
  started_at: number | null
  completed_at: number | null
}

// Store state
state: {
  teamsPanelOpen: boolean      // Whether the split panel is visible
  currentWorkflow: WorkflowState | null
  teams: AgentTeamResponse[]   // Cached team list for Manage tab
  activeTab: 'running' | 'manage'
}

// Actions
actions: {
  // WebSocket event handlers
  handleWorkflowStart(payload)
  handleWorkflowAgentStart(payload)
  handleWorkflowAgentToolCall(payload)
  handleWorkflowAgentProgress(payload)
  handleWorkflowAgentComplete(payload)
  handleWorkflowComplete(payload)
  handleWorkflowError(payload)

  // Panel management
  toggleTeamsPanel()
  openTeamsPanel()
  closeTeamsPanel()

  // Team CRUD
  fetchTeams()
  createTeam(data)
  updateTeam(id, data)
  deleteTeam(id)
  toggleTeamActive(id)
  getTeamConfig(id)
  updateTeamConfig(id, data)
  resetTeamConfig(id)
}
```

### 3.4 Sub-Agent Slot Component

**File**: `frontend/src/modules/teams/SubAgentSlot.vue`

Props:
- `agent: SubAgentState`

Structure:
```
┌─────────────────────────────────┐
│ [●] Role · task summary  [3/7] │  ← Header bar
├─────────────────────────────────┤
│                                 │
│   Independent scroll area       │  ← MessageList (filtered messages)
│                                 │
└─────────────────────────────────┘
```

Header contains: status dot, role name, task summary (truncated), tool progress badge, micro progress bar, duration.

Message area: Reuses `MessageItem` component with this agent's `messages` array.

### 3.5 Teams Panel Container

**File**: `frontend/src/modules/teams/SubAgentPanel.vue`

Renders when `teamsPanelOpen` is true. Contains:
- Tab bar: "运行中" / "管理"
- Running tab: vertically stacked `SubAgentSlot` components (each gets `1/N` height)
- Manage tab: team list + CRUD (see Section 3.6)

### 3.6 Team Management Components

**File**: `frontend/src/modules/teams/TeamManager.vue`

Team list view:
- Each team card shows: name, mode badge, member summary, active toggle
- Actions: edit, delete, execute

**File**: `frontend/src/modules/teams/TeamEditor.vue` (modal)

Create/edit team form:
- Name input
- Mode selector (Pipeline / Graph / Council)
- Toggles: enable_skills, cross_review (council only)
- Team model config section (model, provider, temperature, max_tokens, api_key, api_base)
- Member list with: role, system_prompt, task, perspective (council), depends_on (graph), condition (graph)
- Member reorder (drag or up/down buttons)
- Add/remove member buttons

### 3.7 Draggable Divider

**File**: `frontend/src/modules/teams/TeamsDivider.vue`

- Thin vertical bar (4px highlight area) between chat and sub-agents
- Mouse drag handler: tracks mousemove, updates split ratio
- Visual feedback: highlight on hover, show width tooltip during drag
- Constraints: 30% ~ 70% on either side
- Persist to localStorage key `aie-teams-split-ratio`
- Cursor: `col-resize`

### 3.8 Auto-Open Behavior

When a `workflow_start` event arrives and `teamsPanelOpen` is false:
- Auto-open the Teams panel
- Switch to "运行中" tab

When `workflow_complete` or `workflow_error` arrives:
- Keep panel open (user can review results)
- Update badge to show completed state

User can manually close the panel at any time, even during a running workflow. The workflow continues in the background; the panel can be reopened.

### 3.9 Reconnection / State Recovery

On WebSocket reconnect (browser refresh, network drop):
1. Frontend sends `get_status` request to backend
2. Backend returns: currently running workflows with agent states
3. teamsStore hydrates from this response
4. If a workflow is active, auto-open Teams panel

This is a lightweight recovery — detailed message history for each sub-agent is lost on refresh (acceptable for v1). The TaskBoard retains the workflow task entry which can be clicked to see final results.

### 3.10 i18n Keys

New keys needed (zh-CN and en-US):
- `teams.title` — "Teams" / "团队"
- `teams.running` — "Running" / "运行中"
- `teams.manage` — "Manage" / "管理"
- `teams.createTeam` — "Create Team" / "创建团队"
- `teams.editTeam` — "Edit Team" / "编辑团队"
- `teams.deleteTeam` — "Delete Team" / "删除团队"
- `teams.agentStatus.running` — "Running" / "运行中"
- `teams.agentStatus.waiting` — "Waiting" / "等待中"
- `teams.agentStatus.queued` — "Queued" / "排队"
- `teams.agentStatus.completed` — "Completed" / "已完成"
- `teams.agentStatus.error` — "Error" / "失败"
- `teams.mode.pipeline` / `graph` / `council`
- `teams.noActiveWorkflow` — "No active workflow" / "暂无运行中的工作流"
- `teams.emptyTeams` — "No teams configured" / "暂无团队"

---

## 4. Out of Scope (Deferred)

The following items are noted for future work but NOT included in this implementation:

1. **Config enhancements** (EnhancedModelConfig types, ToolHistoryConfig, output_language) — independent of Teams, tracked separately
2. **ClientMessage attachments** — already exists in connection.py
3. **Channel multi-bot configuration** — significant backend change, separate effort
4. **Enhanced model type routing** — requires config schema refactor
5. **Full message history recovery on refresh** — v2 enhancement
6. **Workflow visualization** (Mermaid DAG rendering) — v2 enhancement

---

## 5. Implementation Phases (Revised — Delta Only)

| Phase | Content | Type |
|-------|---------|------|
| **P1** | Add `workflow_start`/`workflow_complete`/`workflow_error` events to WorkflowEngine | Backend modify |
| **P2** | Add `condition` field to `AgentDefinition` Pydantic schema | Backend modify |
| **P3** | ContextBuilder: team injection + mention detection | Backend modify |
| **P4** | WebSocket: new workflow event message types + handlers | Backend modify |
| **P5** | `teamsStore` Pinia store (state, actions, WS event mapping) | Frontend new |
| **P6** | `TeamsDivider` draggable split component | Frontend new |
| **P7** | `SubAgentSlot` component (per-agent view with independent scroll) | Frontend new |
| **P8** | `SubAgentPanel` container (tabs: running + manage) | Frontend new |
| **P9** | `TeamManager` + `TeamEditor` (CRUD UI) | Frontend new |
| **P10** | ChatWindow integration (Teams button, split layout, WS event wiring) | Frontend modify |
| **P11** | i18n keys (zh-CN + en-US) | Frontend modify |
| **P12** | End-to-end testing and polish | QA |

P1-P4 backend, P5-P11 frontend, P12 testing.
