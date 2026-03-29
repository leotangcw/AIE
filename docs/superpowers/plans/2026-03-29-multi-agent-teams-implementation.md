# Multi-Agent Teams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate CountBot v0.5.0 multi-agent orchestration into AIE with a split-panel Teams UI that shows live sub-agent views alongside the main chat.

**Architecture:** The middle chat area splits horizontally when Teams is active — chat on the left (55%), sub-agent slots on the right (45%) with a draggable divider. Backend WorkflowEngine gains lifecycle events (workflow_start/complete/error). ContextBuilder gets team injection and mention detection. A new `teamsStore` drives the frontend via WebSocket events.

**Tech Stack:** Python/FastAPI (backend), Vue 3/TypeScript/Pinia (frontend), WebSocket (real-time)

---

## File Structure

### Backend — Modify
- `backend/modules/agent/workflow.py` — Add workflow_start/workflow_complete/workflow_error events
- `backend/api/agent_teams.py` — Add `condition` field to AgentDefinition schema
- `backend/modules/agent/context.py` — Team system prompt injection + mention detection

### Frontend — New
- `frontend/src/api/agentTeams.ts` — API client for agent teams CRUD
- `frontend/src/store/teams.ts` — Pinia store (workflow state, team CRUD, WS events)
- `frontend/src/modules/teams/SubAgentSlot.vue` — Per-agent view with independent scroll
- `frontend/src/modules/teams/TeamsDivider.vue` — Draggable split divider
- `frontend/src/modules/teams/SubAgentPanel.vue` — Container with running/manage tabs
- `frontend/src/modules/teams/TeamManager.vue` — Team list CRUD UI
- `frontend/src/modules/teams/TeamEditor.vue` — Team create/edit modal

### Frontend — Modify
- `frontend/src/modules/chat/ChatWindow.vue` — Teams button, split layout, WS event wiring
- `frontend/src/i18n/locales/zh-CN.json` — Chinese translations
- `frontend/src/i18n/locales/en-US.json` — English translations

---

## Task 1: Add Workflow Lifecycle Events to WorkflowEngine

**Files:**
- Modify: `backend/modules/agent/workflow.py`

- [ ] **Step 1: Add workflow_start event at the beginning of `run_pipeline`**

First, add `team_name` to the `__init__` method (after existing params, ~line 50):
```python
def __init__(self, ..., team_name: str | None = None):
    ...
    self._team_name = team_name or "untitled"
```

Then update the `execute_workflow` caller in `backend/api/agent_teams.py` (~line 295) to pass `team_name`:
```python
engine = WorkflowEngine(
    ...,
    team_name=team.name,
)
```

Now add workflow_start events.

After the empty-stages guard in `run_pipeline` (around line 276), add:
```python
await self._emit_ws("workflow_start", mode="pipeline", team_name=self._team_name, goal=goal,
                     agents=[{"id": s.get("id", ""), "role": s.get("role", ""), "task": s.get("task", "")} for s in stages])
```

- [ ] **Step 2: Add workflow_start event at the beginning of `run_graph`**

After the empty-slots guard (around line 330), add:
```python
await self._emit_ws("workflow_start", mode="graph", team_name=self._team_name, goal=goal,
                     agents=[{"id": s.get("id", ""), "role": s.get("role", ""), "task": s.get("task", "")} for s in slots])
```

- [ ] **Step 3: Add workflow_start event at the beginning of `run_council`**

After the empty-members guard (around line 476), add:
```python
await self._emit_ws("workflow_start", mode="council", team_name=self._team_name, question=question,
                     agents=[{"id": m.get("id", ""), "role": m.get("role", ""), "task": m.get("task", "")} for m in members])
```

- [ ] **Step 4: Add workflow_complete event before each method's final return**

In `run_pipeline` (before the final return, ~line 321):
```python
await self._emit_ws("workflow_complete", mode="pipeline", goal=goal)
```

In `run_graph` (before the final return, ~line 460):
```python
await self._emit_ws("workflow_complete", mode="graph", goal=goal)
```

In `run_council` (before both final returns — with and without cross_review, ~lines 539 and 594):
```python
await self._emit_ws("workflow_complete", mode="council", question=question)
```

- [ ] **Step 5: Add workflow_error in exception handlers**

Wrap the agent invocation loop in each `run_*` method with try/except to catch and emit errors. Add at each except block:
```python
await self._emit_ws("workflow_error", mode=mode, agent_id=agent_id, error=str(exc))
raise  # re-raise after emitting
```

- [ ] **Step 6: Commit**

```bash
git add backend/modules/agent/workflow.py
git commit -m "feat: add workflow_start/complete/error lifecycle events to WorkflowEngine"
```

---

## Task 2: Add `condition` Field to AgentDefinition

**Files:**
- Modify: `backend/api/agent_teams.py:35-49`

- [ ] **Step 1: Add `condition` field to `AgentDefinition` Pydantic model**

The `WorkflowEngine._evaluate_condition()` expects a dict with keys `type`, `node`, `text`. The `condition` field must be `Optional[dict]` to match the engine, not a string.

After the `depends_on` field (line 49), add:
```python
condition: Optional[dict] = Field(
    None,
    description=(
        "Conditional expression for execution (graph mode). "
        "Expected format: {\"type\": \"output_contains\", \"text\": \"expected content\"}. "
        "Supported types: output_contains, output_not_contains."
    ),
)
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/agent_teams.py
git commit -m "feat: add condition field to AgentDefinition for graph mode"
```

---

## Task 3: ContextBuilder Team Injection + Mention Detection

**Files:**
- Modify: `backend/modules/agent/context.py`

- [ ] **Step 1: Add `_get_active_teams_section()` method**

Add after the existing `_get_identity()` method (~after line 235). Use synchronous `SessionLocal()` following the same pattern as `_get_personality_from_db()` (line 71) to avoid async issues:
```python
def _get_active_teams_section(self) -> str:
    """Build system prompt section listing active agent teams."""
    try:
        from backend.database import SessionLocal
        from backend.models.agent_team import AgentTeam
        from sqlalchemy import select

        with SessionLocal() as session:
            result = session.execute(
                select(AgentTeam).where(AgentTeam.is_active == True).order_by(AgentTeam.name)  # noqa: E712
            )
            teams = result.scalars().all()
    except Exception:
        return ""

    if not teams:
        return ""

    lines = ["## 可用团队\n", "当前激活的团队（在消息中 @团队名 可调用）：\n"]
    for team in teams:
        agents = team.agents or []
        member_summary = ", ".join(
            a.get("role", a.get("id", "?")) for a in agents
        )
        lines.append(f"### {team.name} ({team.mode})\n")
        lines.append(f"- 成员: {member_summary}\n")
    return "\n".join(lines)
```

- [ ] **Step 2: Integrate teams section into `build_system_prompt()`**

In `build_system_prompt()` (line 30), after building parts but before the final join, add the teams section:
```python
# After line ~50 (after skills summary, before join)
teams_section = self._get_active_teams_section()
if teams_section:
    parts.append(teams_section)
```

- [ ] **Step 3: Add `_find_mentioned_team()` method**

```python
def _find_mentioned_team(self, user_message: str) -> str | None:
    """Scan user message for @team_name or 使用[team_name] mentions."""
    try:
        from backend.database import SessionLocal
        from backend.models.agent_team import AgentTeam
        from sqlalchemy import select

        with SessionLocal() as session:
            result = session.execute(
                select(AgentTeam).where(AgentTeam.is_active == True)  # noqa: E712
            )
            teams = result.scalars().all()
    except Exception:
        return None

    for team in teams:
        if f"@{team.name}" in user_message or f"@{team.name.lower()}" in user_message:
            return team.name
        if f"使用{team.name}" in user_message or f"使用[{team.name}]" in user_message:
            return team.name
    return None
```

- [ ] **Step 4: Integrate mention detection into `build_messages()`**

In `build_messages()` (line 237), after building the history messages but before the anti-hallucination reminder, add:
```python
# After line ~259 (after extending with history), before the reminder block
mentioned_team = self._find_mentioned_team(current_message)
if mentioned_team:
    messages.append({
        "role": "system",
        "content": f"检测到用户提及团队「{mentioned_team}」，建议使用 workflow_run 工具调用该团队来处理当前任务。"
    })
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/agent/context.py
git commit -m "feat: add team injection and mention detection to ContextBuilder"
```

---

## Task 4: Create Agent Teams API Client (Frontend)

**Files:**
- Create: `frontend/src/api/agentTeams.ts`

- [ ] **Step 1: Create API client file**

```typescript
import apiClient from './client'

export interface AgentDefinition {
    id: string
    role: string
    system_prompt?: string
    task: string
    perspective?: string
    depends_on?: string[]
    condition?: string
}

export interface AgentTeamResponse {
    id: string
    name: string
    description?: string
    mode: 'pipeline' | 'graph' | 'council'
    agents: AgentDefinition[]
    is_active: boolean
    cross_review: boolean
    enable_skills: boolean
    use_custom_model: boolean
    created_at: string
    updated_at: string
}

export interface AgentTeamCreateRequest {
    name: string
    description?: string
    mode: 'pipeline' | 'graph' | 'council'
    agents: AgentDefinition[]
    is_active?: boolean
    cross_review?: boolean
    enable_skills?: boolean
}

export interface AgentTeamUpdateRequest {
    name?: string
    description?: string
    mode?: 'pipeline' | 'graph' | 'council'
    agents?: AgentDefinition[]
    is_active?: boolean
    cross_review?: boolean
    enable_skills?: boolean
}

export interface TeamModelConfig {
    provider?: string
    model?: string
    temperature?: number
    max_tokens?: number
    api_key?: string
    api_base?: string
}

export interface TeamModelConfigResponse {
    team_id: string
    use_custom_model: boolean
    model_settings: Record<string, any>
    global_defaults: Record<string, any>
}

export const agentTeamsAPI = {
    list: (): Promise<AgentTeamResponse[]> =>
        apiClient.get('/agent-teams/'),

    get: (id: string): Promise<AgentTeamResponse> =>
        apiClient.get(`/agent-teams/${id}`),

    create: (data: AgentTeamCreateRequest): Promise<AgentTeamResponse> =>
        apiClient.post('/agent-teams/', data),

    update: (id: string, data: AgentTeamUpdateRequest): Promise<AgentTeamResponse> =>
        apiClient.put(`/agent-teams/${id}`, data),

    delete: (id: string): Promise<void> =>
        apiClient.delete(`/agent-teams/${id}`),

    getConfig: (id: string): Promise<TeamModelConfigResponse> =>
        apiClient.get(`/agent-teams/${id}/config`),

    updateConfig: (id: string, data: TeamModelConfig): Promise<any> =>
        apiClient.put(`/agent-teams/${id}/config`, data),

    resetConfig: (id: string): Promise<any> =>
        apiClient.delete(`/agent-teams/${id}/config`),
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/agentTeams.ts
git commit -m "feat: add agent teams API client"
```

---

## Task 5: Create teamsStore (Pinia)

**Files:**
- Create: `frontend/src/store/teams.ts`

- [ ] **Step 1: Create the teams store with state, computed, and actions**

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { agentTeamsAPI, type AgentTeamResponse, type TeamModelConfig } from '@/api/agentTeams'

export interface SubAgentMessage {
    role: 'assistant' | 'system' | 'tool'
    content: string
    tool_name?: string
    tool_result?: string
    is_thinking?: boolean
    timestamp?: number
}

export interface SubAgentState {
    agent_id: string
    role: string
    task: string
    status: 'queued' | 'running' | 'waiting' | 'completed' | 'error'
    progress: number
    tool_count: number
    tool_name: string | null
    messages: SubAgentMessage[]
    duration: number
    started_at: number | null
    completed_at: number | null
    error: string | null
}

export interface WorkflowState {
    team_name: string
    mode: 'pipeline' | 'graph' | 'council'
    agents: SubAgentState[]
    started_at: number | null
    completed_at: number | null
    error: string | null
}

export const useTeamsStore = defineStore('teams', () => {
    // State
    const teamsPanelOpen = ref(false)
    const activeTab = ref<'running' | 'manage'>('running')
    const currentWorkflow = ref<WorkflowState | null>(null)
    const teams = ref<AgentTeamResponse[]>([])
    const splitRatio = ref(0.55) // chat side ratio
    const loading = ref(false)

    // Computed
    const isWorkflowActive = computed(() => {
        const wf = currentWorkflow.value
        return wf !== null && wf.completed_at === null && wf.error === null
    })

    const runningAgentCount = computed(() => {
        if (!currentWorkflow.value) return 0
        return currentWorkflow.value.agents.filter(a => a.status === 'running' || a.status === 'waiting').length
    })

    // -- Workflow event handlers --

    function handleWorkflowStart(data: any) {
        currentWorkflow.value = {
            team_name: data.team_name || data.goal || '',
            mode: data.mode || 'pipeline',
            agents: (data.agents || []).map((a: any) => ({
                agent_id: a.id || a.agent_id || '',
                role: a.role || '',
                task: a.task || '',
                status: 'queued' as const,
                progress: 0,
                tool_count: 0,
                tool_name: null,
                messages: [],
                duration: 0,
                started_at: null,
                completed_at: null,
                error: null,
            })),
            started_at: Date.now(),
            completed_at: null,
            error: null,
        }
        // Auto-open panel
        teamsPanelOpen.value = true
        activeTab.value = 'running'
    }

    function handleWorkflowAgentStart(data: any) {
        if (!currentWorkflow.value) return
        const agent = currentWorkflow.value.agents.find(a => a.agent_id === data.agent_id)
        if (agent) {
            agent.status = 'running'
            agent.started_at = Date.now()
            agent.task = data.task || agent.task
        }
    }

    function handleWorkflowAgentToolCall(data: any) {
        if (!currentWorkflow.value) return
        const agent = currentWorkflow.value.agents.find(a => a.agent_id === data.agent_id)
        if (agent) {
            agent.tool_count++
            agent.tool_name = data.tool_name
            // Add tool call message
            agent.messages.push({
                role: 'tool',
                content: data.arguments || '',
                tool_name: data.tool_name,
                timestamp: Date.now(),
            })
        }
    }

    function handleWorkflowAgentProgress(data: any) {
        if (!currentWorkflow.value) return
        const agent = currentWorkflow.value.agents.find(a => a.agent_id === data.agent_id)
        if (agent) {
            agent.progress = data.progress || 0
        }
    }

    function handleWorkflowAgentToolResult(data: any) {
        if (!currentWorkflow.value) return
        const agent = currentWorkflow.value.agents.find(a => a.agent_id === data.agent_id)
        if (agent && agent.messages.length > 0) {
            const lastMsg = agent.messages[agent.messages.length - 1]
            if (lastMsg.role === 'tool') {
                lastMsg.tool_result = data.result
            }
        }
    }

    function handleWorkflowAgentChunk(data: any) {
        if (!currentWorkflow.value) return
        const agent = currentWorkflow.value.agents.find(a => a.agent_id === data.agent_id)
        if (agent) {
            // Append to last assistant message or create new one
            const lastMsg = agent.messages[agent.messages.length - 1]
            if (lastMsg && lastMsg.role === 'assistant' && !lastMsg.tool_name) {
                lastMsg.content += data.content || ''
            } else {
                agent.messages.push({
                    role: 'assistant',
                    content: data.content || '',
                    timestamp: Date.now(),
                })
            }
        }
    }

    function handleWorkflowAgentComplete(data: any) {
        if (!currentWorkflow.value) return
        const agent = currentWorkflow.value.agents.find(a => a.agent_id === data.agent_id)
        if (agent) {
            agent.status = 'completed'
            agent.completed_at = Date.now()
            agent.duration = agent.started_at ? Math.floor((Date.now() - agent.started_at) / 1000) : 0
            agent.progress = 100
            agent.messages.push({
                role: 'system',
                content: `[完成] ${data.result_summary || ''}`,
                timestamp: Date.now(),
            })
        }
    }

    function handleWorkflowComplete(data: any) {
        if (!currentWorkflow.value) return
        currentWorkflow.value.completed_at = Date.now()
        // Mark any remaining queued/running agents as completed
        currentWorkflow.value.agents.forEach(a => {
            if (a.status === 'queued' || a.status === 'running' || a.status === 'waiting') {
                a.status = 'completed'
                a.completed_at = Date.now()
                a.duration = a.started_at ? Math.floor((Date.now() - a.started_at) / 1000) : 0
                a.progress = 100
            }
        })
    }

    function handleWorkflowError(data: any) {
        if (!currentWorkflow.value) return
        currentWorkflow.value.error = data.error
        currentWorkflow.value.completed_at = Date.now()
        if (data.agent_id) {
            const agent = currentWorkflow.value.agents.find(a => a.agent_id === data.agent_id)
            if (agent) {
                agent.status = 'error'
                agent.error = data.error
                agent.completed_at = Date.now()
            }
        }
    }

    function handleWorkflowEvent(type: string, data: any) {
        switch (type) {
            case 'workflow_start': handleWorkflowStart(data); break
            case 'workflow_agent_start': handleWorkflowAgentStart(data); break
            case 'workflow_agent_tool_call': handleWorkflowAgentToolCall(data); break
            case 'workflow_agent_progress': handleWorkflowAgentProgress(data); break
            case 'workflow_agent_tool_result': handleWorkflowAgentToolResult(data); break
            case 'workflow_agent_chunk': handleWorkflowAgentChunk(data); break
            case 'workflow_agent_complete': handleWorkflowAgentComplete(data); break
            case 'workflow_complete': handleWorkflowComplete(data); break
            case 'workflow_error': handleWorkflowError(data); break
        }
    }

    // -- Panel management --

    function toggleTeamsPanel() {
        teamsPanelOpen.value = !teamsPanelOpen.value
    }

    function openTeamsPanel() {
        teamsPanelOpen.value = true
        activeTab.value = 'running'
    }

    function closeTeamsPanel() {
        teamsPanelOpen.value = false
    }

    // -- Team CRUD --

    async function fetchTeams() {
        try {
            teams.value = await agentTeamsAPI.list()
        } catch (e) {
            console.error('Failed to fetch teams:', e)
        }
    }

    async function createTeam(data: any) {
        loading.value = true
        try {
            const team = await agentTeamsAPI.create(data)
            teams.value.unshift(team)
            return team
        } finally {
            loading.value = false
        }
    }

    async function updateTeam(id: string, data: any) {
        loading.value = true
        try {
            const team = await agentTeamsAPI.update(id, data)
            const idx = teams.value.findIndex(t => t.id === id)
            if (idx >= 0) teams.value[idx] = team
            return team
        } finally {
            loading.value = false
        }
    }

    async function deleteTeam(id: string) {
        loading.value = true
        try {
            await agentTeamsAPI.delete(id)
            teams.value = teams.value.filter(t => t.id !== id)
        } finally {
            loading.value = false
        }
    }

    async function toggleTeamActive(id: string) {
        const team = teams.value.find(t => t.id === id)
        if (!team) return
        await updateTeam(id, { is_active: !team.is_active })
    }

    async function getTeamConfig(id: string) {
        return agentTeamsAPI.getConfig(id)
    }

    async function updateTeamConfig(id: string, data: TeamModelConfig) {
        return agentTeamsAPI.updateConfig(id, data)
    }

    async function resetTeamConfig(id: string) {
        return agentTeamsAPI.resetConfig(id)
    }

    // Init
    function init() {
        // Restore split ratio from localStorage
        const saved = localStorage.getItem('aie-teams-split-ratio')
        if (saved) splitRatio.value = parseFloat(saved)

        // Load teams for manage tab
        fetchTeams()
    }

    return {
        teamsPanelOpen, activeTab, currentWorkflow, teams, splitRatio, loading,
        isWorkflowActive, runningAgentCount,
        handleWorkflowEvent,
        toggleTeamsPanel, openTeamsPanel, closeTeamsPanel,
        fetchTeams, createTeam, updateTeam, deleteTeam, toggleTeamActive,
        getTeamConfig, updateTeamConfig, resetTeamConfig,
        init,
    }
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/store/teams.ts
git commit -m "feat: add teamsStore Pinia store with workflow event handling"
```

---

## Task 6: Create TeamsDivider Component

**Files:**
- Create: `frontend/src/modules/teams/TeamsDivider.vue`

- [ ] **Step 1: Create the draggable divider component**

```vue
<template>
  <div
    class="teams-divider"
    :class="{ dragging: isDragging }"
    @mousedown="startDrag"
  >
    <div class="divider-line" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  modelValue: number  // chat side ratio (0.3 - 0.7)
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

const isDragging = ref(false)

function startDrag(e: MouseEvent) {
  e.preventDefault()
  isDragging.value = true

  const container = document.querySelector('.chat-pane') as HTMLElement
  if (!container) return

  const onMove = (ev: MouseEvent) => {
    const rect = container.getBoundingClientRect()
    const offset = ev.clientX - rect.left
    const ratio = Math.max(0.3, Math.min(0.7, offset / rect.width))
    emit('update:modelValue', ratio)
  }

  const onUp = () => {
    isDragging.value = false
    localStorage.setItem('aie-teams-split-ratio', String(props.modelValue))
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }

  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}
</script>

<style scoped>
.teams-divider {
  width: 6px;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 1px;
  flex-shrink: 0;
  user-select: none;
  z-index: 10;
  transition: background-color 0.15s;
}
.teams-divider:hover,
.teams-divider.dragging {
  background-color: var(--accent-color, #7c3aed);
}
.divider-line {
  width: 2px;
  height: 32px;
  border-radius: 1px;
  background-color: var(--border-color, #333);
  opacity: 0.6;
}
.teams-divider:hover .divider-line,
.teams-divider.dragging .divider-line {
  background-color: white;
  opacity: 0.5;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/teams/TeamsDivider.vue
git commit -m "feat: add TeamsDivider draggable split component"
```

---

## Task 7: Create SubAgentSlot Component

**Files:**
- Create: `frontend/src/modules/teams/SubAgentSlot.vue`

- [ ] **Step 1: Create the per-agent view component**

```vue
<template>
  <div class="subagent-slot" :class="[`status-${agent.status}`]">
    <!-- Header -->
    <div class="slot-header">
      <div class="slot-header-left">
        <span class="status-dot" :class="agent.status" />
        <span class="agent-role">{{ agent.role || agent.agent_id }}</span>
        <span class="agent-task">{{ truncatedTask }}</span>
      </div>
      <div class="slot-header-right">
        <span v-if="agent.status === 'running' || agent.status === 'completed'" class="tool-badge">
          {{ agent.tool_count }}/{{ agent.tool_name || '...' }}
        </span>
        <span class="status-label" :class="agent.status">{{ statusLabel }}</span>
        <span v-if="agent.duration > 0" class="duration-badge">{{ formatDuration(agent.duration) }}</span>
      </div>
    </div>
    <!-- Progress bar -->
    <div v-if="agent.status === 'running'" class="slot-progress">
      <div class="progress-bar" :style="{ width: `${agent.progress}%` }" />
    </div>
    <!-- Messages -->
    <div class="slot-messages" ref="messagesRef">
      <div v-if="agent.messages.length === 0" class="slot-empty">
        {{ emptyText }}
      </div>
      <div
        v-for="(msg, idx) in agent.messages"
        :key="idx"
        class="slot-message"
        :class="`msg-${msg.role}`"
      >
        <!-- Tool call -->
        <template v-if="msg.role === 'tool'">
          <div class="msg-tool-call">
            <span class="tool-icon">&#9881;</span>
            <span class="tool-name">{{ msg.tool_name }}</span>
          </div>
          <div v-if="msg.tool_result" class="msg-tool-result">
            {{ truncateText(msg.tool_result, 200) }}
          </div>
        </template>
        <!-- System message -->
        <template v-else-if="msg.role === 'system'">
          <div class="msg-system">{{ msg.content }}</div>
        </template>
        <!-- Assistant message -->
        <template v-else>
          <div class="msg-assistant">{{ msg.content }}</div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import type { SubAgentState } from '@/store/teams'

const props = defineProps<{
  agent: SubAgentState
}>()

const messagesRef = ref<HTMLElement | null>(null)

const truncatedTask = computed(() => {
  const task = props.agent.task
  return task.length > 30 ? task.slice(0, 30) + '...' : task
})

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    queued: '排队中', running: '运行中', waiting: '等待中',
    completed: '已完成', error: '失败',
  }
  return map[props.agent.status] || props.agent.status
})

const emptyText = computed(() => {
  const map: Record<string, string> = {
    queued: '等待前序任务完成...', running: '正在处理...', waiting: '等待中...',
    completed: '已结束', error: '执行失败',
  }
  return map[props.agent.status] || ''
})

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s}s`
}

function truncateText(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '...' : text
}

// Auto-scroll on new messages
watch(() => props.agent.messages.length, async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
})
</script>

<style scoped>
.subagent-slot {
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid var(--border-color, #222);
  min-height: 0;
  overflow: hidden;
}
.slot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: var(--bg-secondary, #161628);
  border-bottom: 1px solid var(--border-color, #222);
  flex-shrink: 0;
  gap: 8px;
}
.slot-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.queued { background: #555; }
.status-dot.running { background: #4ade80; animation: pulse 1.5s infinite; }
.status-dot.waiting { background: #facc15; }
.status-dot.completed { background: #4ade80; }
.status-dot.error { background: #ef4444; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.agent-role {
  font-weight: 600;
  font-size: 12px;
  color: var(--text-primary, #e2e8f0);
  flex-shrink: 0;
}
.agent-task {
  font-size: 11px;
  color: var(--text-secondary, #94a3b8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.slot-header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.tool-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(124, 58, 237, 0.2);
  color: #a78bfa;
}
.status-label {
  font-size: 10px;
  font-weight: 500;
}
.status-label.running { color: #4ade80; }
.status-label.waiting { color: #facc15; }
.status-label.completed { color: #4ade80; }
.status-label.error { color: #ef4444; }
.status-label.queued { color: #555; }
.duration-badge {
  font-size: 10px;
  color: var(--text-tertiary, #555);
}
.slot-progress {
  height: 2px;
  background: var(--bg-tertiary, #222);
  flex-shrink: 0;
}
.progress-bar {
  height: 100%;
  background: #7c3aed;
  border-radius: 1px;
  transition: width 0.3s;
}
.slot-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
  min-height: 0;
}
.slot-empty {
  color: var(--text-tertiary, #555);
  font-size: 11px;
  text-align: center;
  padding: 16px 0;
}
.slot-message {
  margin-bottom: 6px;
  font-size: 11px;
  line-height: 1.5;
}
.msg-tool-call {
  color: #a78bfa;
}
.msg-tool-call .tool-icon {
  margin-right: 4px;
}
.msg-tool-result {
  color: var(--text-tertiary, #666);
  margin-top: 2px;
  padding-left: 18px;
  font-size: 10px;
  white-space: pre-wrap;
  word-break: break-all;
}
.msg-system {
  color: var(--text-secondary, #888);
  font-style: italic;
}
.msg-assistant {
  color: var(--text-primary, #e2e8f0);
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/teams/SubAgentSlot.vue
git commit -m "feat: add SubAgentSlot per-agent view component"
```

---

## Task 8: Create SubAgentPanel Container

**Files:**
- Create: `frontend/src/modules/teams/SubAgentPanel.vue`

- [ ] **Step 1: Create the panel container with running/manage tabs**

```vue
<template>
  <div class="sub-agent-panel">
    <!-- Tab bar -->
    <div class="panel-tabs">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'running' }"
        @click="activeTab = 'running'"
      >
        运行中
        <span v-if="runningAgentCount > 0" class="tab-badge">{{ runningAgentCount }}</span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'manage' }"
        @click="activeTab = 'manage'"
      >
        管理
      </button>
    </div>

    <!-- Running tab -->
    <div v-if="activeTab === 'running'" class="panel-content running-content">
      <template v-if="currentWorkflow && currentWorkflow.agents.length > 0">
        <div class="workflow-header">
          <span class="workflow-mode">{{ currentWorkflow.mode }}</span>
          <span class="workflow-name">{{ currentWorkflow.team_name }}</span>
        </div>
        <SubAgentSlot
          v-for="agent in currentWorkflow.agents"
          :key="agent.agent_id"
          :agent="agent"
        />
      </template>
      <div v-else class="empty-state">
        <p>暂无运行中的工作流</p>
        <p class="empty-hint">通过 @团队名 调用团队，或使用 workflow_run 工具</p>
      </div>
    </div>

    <!-- Manage tab -->
    <div v-if="activeTab === 'manage'" class="panel-content manage-content">
      <TeamManager />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTeamsStore } from '@/store/teams'
import SubAgentSlot from './SubAgentSlot.vue'
import TeamManager from './TeamManager.vue'

const teamsStore = useTeamsStore()

const activeTab = computed({
  get: () => teamsStore.activeTab,
  set: (v) => { teamsStore.activeTab = v },
})

const currentWorkflow = computed(() => teamsStore.currentWorkflow)
const runningAgentCount = computed(() => teamsStore.runningAgentCount)
</script>

<style scoped>
.sub-agent-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary, #0f0f1a);
  overflow: hidden;
}
.panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color, #222);
  flex-shrink: 0;
  padding: 0 8px;
}
.tab-btn {
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary, #888);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
}
.tab-btn:hover {
  color: var(--text-primary, #e2e8f0);
}
.tab-btn.active {
  color: var(--accent-color, #7c3aed);
  border-bottom-color: var(--accent-color, #7c3aed);
}
.tab-badge {
  font-size: 10px;
  background: var(--accent-color, #7c3aed);
  color: white;
  padding: 0 5px;
  border-radius: 8px;
  min-width: 16px;
  text-align: center;
}
.panel-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.running-content {
  overflow-y: auto;
}
.workflow-header {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color, #222);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.workflow-mode {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(124, 58, 237, 0.15);
  color: #a78bfa;
  text-transform: uppercase;
}
.workflow-name {
  font-size: 12px;
  color: var(--text-primary, #e2e8f0);
  font-weight: 500;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary, #555);
}
.empty-state p {
  margin: 4px 0;
  font-size: 13px;
}
.empty-hint {
  font-size: 11px !important;
}
.manage-content {
  overflow-y: auto;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/modules/teams/SubAgentPanel.vue
git commit -m "feat: add SubAgentPanel container with running/manage tabs"
```

---

## Task 9: Create TeamManager + TeamEditor Components

**Files:**
- Create: `frontend/src/modules/teams/TeamManager.vue`
- Create: `frontend/src/modules/teams/TeamEditor.vue`

- [ ] **Step 1: Create TeamManager.vue (team list + CRUD)**

```vue
<template>
  <div class="team-manager">
    <div class="manager-header">
      <h3>团队模板</h3>
      <button class="btn-create" @click="showEditor(null)">
        + 创建团队
      </button>
    </div>

    <div v-if="teamsStore.loading" class="loading">加载中...</div>

    <div v-else-if="teams.length === 0" class="empty">
      暂无团队，点击上方按钮创建
    </div>

    <div v-else class="team-list">
      <div
        v-for="team in teams"
        :key="team.id"
        class="team-card"
        :class="{ inactive: !team.is_active }"
      >
        <div class="team-card-header">
          <div class="team-info">
            <span class="team-name">{{ team.name }}</span>
            <span class="mode-badge">{{ team.mode }}</span>
            <span class="member-count">{{ (team.agents || []).length }} 成员</span>
          </div>
          <div class="team-actions">
            <button class="icon-btn-sm" @click="teamsStore.toggleTeamActive(team.id)" :title="team.is_active ? '禁用' : '启用'">
              {{ team.is_active ? '✓' : '○' }}
            </button>
            <button class="icon-btn-sm" @click="showEditor(team)" title="编辑">✎</button>
            <button class="icon-btn-sm danger" @click="handleDelete(team)" title="删除">✕</button>
          </div>
        </div>
        <div class="team-members">
          <span
            v-for="(agent, idx) in (team.agents || [])"
            :key="agent.id || idx"
            class="member-chip"
          >
            {{ agent.role || agent.id }}
            <span v-if="team.mode === 'graph' && agent.depends_on?.length" class="dep-hint">
              ← {{ agent.depends_on.join(', ') }}
            </span>
          </span>
        </div>
      </div>
    </div>

    <!-- Editor Modal -->
    <TeamEditor
      v-if="editingTeam !== undefined"
      :team="editingTeam"
      @close="editingTeam = undefined"
      @saved="onSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTeamsStore } from '@/store/teams'
import TeamEditor from './TeamEditor.vue'
import type { AgentTeamResponse } from '@/api/agentTeams'

const teamsStore = useTeamsStore()

const teams = computed(() => teamsStore.teams)
const editingTeam = ref<AgentTeamResponse | null | undefined>(undefined)

function showEditor(team: AgentTeamResponse | null) {
  editingTeam.value = team
}

function handleDelete(team: AgentTeamResponse) {
  if (confirm(`确定删除团队「${team.name}」？`)) {
    teamsStore.deleteTeam(team.id)
  }
}

function onSaved() {
  editingTeam.value = undefined
  teamsStore.fetchTeams()
}
</script>

<style scoped>
.team-manager { padding: 12px; }
.manager-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.manager-header h3 {
  font-size: 14px;
  color: var(--text-primary, #e2e8f0);
  margin: 0;
}
.btn-create {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid var(--accent-color, #7c3aed);
  color: var(--accent-color, #7c3aed);
  background: none;
  cursor: pointer;
}
.btn-create:hover {
  background: var(--accent-color, #7c3aed);
  color: white;
}
.loading, .empty {
  text-align: center;
  color: var(--text-tertiary, #555);
  font-size: 12px;
  padding: 24px 0;
}
.team-list { display: flex; flex-direction: column; gap: 8px; }
.team-card {
  background: var(--bg-secondary, #161628);
  border-radius: 6px;
  padding: 10px;
  border: 1px solid var(--border-color, #222);
}
.team-card.inactive { opacity: 0.5; }
.team-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.team-info { display: flex; align-items: center; gap: 6px; }
.team-name { font-weight: 600; font-size: 13px; color: var(--text-primary, #e2e8f0); }
.mode-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(124, 58, 237, 0.15);
  color: #a78bfa;
  text-transform: uppercase;
}
.member-count { font-size: 11px; color: var(--text-tertiary, #555); }
.team-actions { display: flex; gap: 4px; }
.icon-btn-sm {
  width: 24px; height: 24px;
  border: none; background: none;
  color: var(--text-secondary, #888);
  cursor: pointer; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px;
}
.icon-btn-sm:hover { background: var(--bg-tertiary, #222); }
.icon-btn-sm.danger:hover { color: #ef4444; }
.team-members { display: flex; flex-wrap: wrap; gap: 4px; }
.member-chip {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 3px;
  background: rgba(96, 165, 250, 0.1);
  color: #60a5fa;
}
.dep-hint { color: var(--text-tertiary, #555); }
</style>
```

- [ ] **Step 2: Create TeamEditor.vue (create/edit modal)**

```vue
<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <h3>{{ isEdit ? '编辑团队' : '创建团队' }}</h3>
        <button class="icon-btn-sm" @click="$emit('close')">✕</button>
      </div>
      <div class="modal-body">
        <!-- Name -->
        <div class="form-group">
          <label>团队名称</label>
          <input v-model="form.name" type="text" placeholder="例如：编程团队" />
        </div>
        <!-- Mode -->
        <div class="form-group">
          <label>编排模式</label>
          <select v-model="form.mode">
            <option value="pipeline">Pipeline（顺序执行）</option>
            <option value="graph">Graph（DAG 依赖图）</option>
            <option value="council">Council（多角度讨论）</option>
          </select>
        </div>
        <!-- Toggles -->
        <div class="form-row">
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.enable_skills" />
            启用技能注入
          </label>
          <label v-if="form.mode === 'council'" class="checkbox-label">
            <input type="checkbox" v-model="form.cross_review" />
            交叉审阅
          </label>
        </div>

        <!-- Members -->
        <div class="members-section">
          <div class="members-header">
            <label>成员列表</label>
            <button class="btn-add" @click="addMember">+ 添加成员</button>
          </div>
          <div
            v-for="(member, idx) in form.agents"
            :key="idx"
            class="member-editor"
          >
            <div class="member-header">
              <span class="member-num">#{{ idx + 1 }}</span>
              <div class="member-actions">
                <button class="icon-btn-sm" :disabled="idx === 0" @click="moveMember(idx, -1)">↑</button>
                <button class="icon-btn-sm" :disabled="idx === form.agents.length - 1" @click="moveMember(idx, 1)">↓</button>
                <button class="icon-btn-sm danger" @click="removeMember(idx)">✕</button>
              </div>
            </div>
            <div class="member-fields">
              <div class="form-row">
                <input v-model="member.id" placeholder="ID (如 planner)" class="field-sm" />
                <input v-model="member.role" placeholder="角色名 (如 规划师)" class="field-lg" />
              </div>
              <textarea v-model="member.system_prompt" placeholder="系统提示词（可选）" rows="2" />
              <textarea v-model="member.task" placeholder="任务描述" rows="2" />
              <div v-if="form.mode === 'council'" class="form-group">
                <input v-model="member.perspective" placeholder="视角（council 模式，如：技术视角）" />
              </div>
              <div v-if="form.mode === 'graph'" class="form-row">
                <input v-model="member.depends_on_str" placeholder="依赖的 Agent ID（逗号分隔，如：planner）" class="field-lg" />
                <input v-model="member.condition_str" placeholder="条件类型（如：output_contains）" class="field-sm" />
                <input v-model="member.condition_text" placeholder="条件内容（如：通过）" class="field-lg" />
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-confirm" :disabled="!form.name" @click="handleSave">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { useTeamsStore } from '@/store/teams'
import type { AgentTeamResponse, AgentDefinition } from '@/api/agentTeams'

const props = defineProps<{
  team: AgentTeamResponse | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const teamsStore = useTeamsStore()
const isEdit = computed(() => props.team !== null)

interface MemberForm extends AgentDefinition {
  depends_on_str?: string
  condition_str?: string
  condition_text?: string
}

function createDefaultMember(): MemberForm {
  return { id: '', role: '', system_prompt: '', task: '', perspective: undefined, depends_on: [], condition: undefined, depends_on_str: '', condition_str: '', condition_text: '' }
}

const form = reactive({
  name: props.team?.name || '',
  mode: (props.team?.mode || 'pipeline') as 'pipeline' | 'graph' | 'council',
  enable_skills: props.team?.enable_skills ?? false,
  cross_review: props.team?.cross_review ?? true,
  agents: (props.team?.agents || []).map(a => ({
    ...a,
    depends_on_str: (a.depends_on || []).join(', '),
    condition_str: (a.condition as any)?.type || '',
    condition_text: (a.condition as any)?.text || '',
  })) as MemberForm[],
})

if (form.agents.length === 0) {
  form.agents.push(createDefaultMember())
}

function addMember() {
  form.agents.push(createDefaultMember())
}

function removeMember(idx: number) {
  form.agents.splice(idx, 1)
}

function moveMember(idx: number, direction: number) {
  const newIdx = idx + direction
  if (newIdx < 0 || newIdx >= form.agents.length) return
  const temp = form.agents[idx]
  form.agents[idx] = form.agents[newIdx]
  form.agents[newIdx] = temp
}

async function handleSave() {
  const agents: AgentDefinition[] = form.agents.map(a => ({
    id: a.id,
    role: a.role,
    system_prompt: a.system_prompt || undefined,
    task: a.task,
    perspective: a.perspective,
    depends_on: a.depends_on_str ? a.depends_on_str.split(',').map(s => s.trim()).filter(Boolean) : [],
    condition: a.condition_str ? { type: a.condition_str, node: '', text: a.condition_text || '' } : undefined,
  }))

  const payload = {
    name: form.name,
    mode: form.mode,
    enable_skills: form.enable_skills,
    cross_review: form.cross_review,
    agents,
  }

  try {
    if (isEdit.value && props.team) {
      await teamsStore.updateTeam(props.team.id, payload)
    } else {
      await teamsStore.createTeam(payload)
    }
    emit('saved')
  } catch (e: any) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 200;
}
.modal {
  background: var(--bg-primary, #1a1a2e);
  border-radius: 12px;
  border: 1px solid var(--border-color, #333);
  width: 560px;
  max-height: 80vh;
  display: flex; flex-direction: column;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color, #333);
}
.modal-header h3 { font-size: 16px; color: var(--text-primary, #e2e8f0); margin: 0; }
.modal-body {
  padding: 16px 20px;
  overflow-y: auto;
  flex: 1;
}
.modal-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border-color, #333);
  display: flex; justify-content: flex-end; gap: 8px;
}
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; color: var(--text-secondary, #888); margin-bottom: 4px; }
.form-group input, .form-group textarea, .form-group select {
  width: 100%; padding: 6px 10px; border-radius: 6px;
  border: 1px solid var(--border-color, #333);
  background: var(--bg-secondary, #0f0f1a);
  color: var(--text-primary, #e2e8f0);
  font-size: 13px;
  box-sizing: border-box;
}
.form-group textarea { resize: vertical; font-family: inherit; }
.form-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.field-sm { width: 120px !important; }
.field-lg { flex: 1 !important; }
.checkbox-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--text-secondary, #888);
  cursor: pointer;
}
.members-section { margin-top: 16px; }
.members-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.members-header label { font-size: 12px; color: var(--text-secondary, #888); }
.btn-add {
  font-size: 11px; padding: 2px 10px; border-radius: 4px;
  border: 1px dashed var(--border-color, #444);
  color: var(--text-secondary, #888); background: none; cursor: pointer;
}
.btn-add:hover { border-color: var(--accent-color, #7c3aed); color: var(--accent-color, #7c3aed); }
.member-editor {
  background: var(--bg-secondary, #0f0f1a);
  border: 1px solid var(--border-color, #222);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 8px;
}
.member-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;
}
.member-num { font-size: 11px; color: var(--text-tertiary, #555); font-weight: 600; }
.member-actions { display: flex; gap: 2px; }
.icon-btn-sm {
  width: 24px; height: 24px; border: none; background: none;
  color: var(--text-secondary, #888); cursor: pointer; border-radius: 3px;
  display: flex; align-items: center; justify-content: center; font-size: 12px;
}
.icon-btn-sm:hover { background: var(--bg-tertiary, #222); }
.icon-btn-sm:disabled { opacity: 0.3; cursor: not-allowed; }
.icon-btn-sm.danger:hover { color: #ef4444; }
.member-fields { display: flex; flex-direction: column; gap: 6px; }
.btn-cancel {
  padding: 6px 16px; border-radius: 6px;
  border: 1px solid var(--border-color, #333);
  color: var(--text-secondary, #888); background: none; cursor: pointer;
}
.btn-confirm {
  padding: 6px 16px; border-radius: 6px;
  border: none; background: var(--accent-color, #7c3aed);
  color: white; cursor: pointer;
}
.btn-confirm:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/modules/teams/TeamManager.vue frontend/src/modules/teams/TeamEditor.vue
git commit -m "feat: add TeamManager list and TeamEditor modal components"
```

---

## Task 10: Integrate Teams into ChatWindow

**Files:**
- Modify: `frontend/src/modules/chat/ChatWindow.vue`

This is the largest task — it wires everything together.

- [ ] **Step 1: Add imports for Teams components and store**

In the existing lucide-vue-next import block (~line 395-438), add `Users` to the import:
```typescript
import { ..., Users, ... } from 'lucide-vue-next'
```

Add new imports after existing imports:
```typescript
import { useTeamsStore } from '@/store/teams'
import SubAgentPanel from '@/modules/teams/SubAgentPanel.vue'
import TeamsDivider from '@/modules/teams/TeamsDivider.vue'
```

- [ ] **Step 2: Initialize teamsStore**

After other store initializations:
```typescript
const teamsStore = useTeamsStore()
teamsStore.init()
```

- [ ] **Step 3: Add Teams button to headerActions computed**

In the `headerActions` computed property (line ~1270), insert after the 'skills' entry (line ~1274) and before the 'experience' entry:
```typescript
{ id: 'teams', icon: Users, label: 'nav.teams', tooltip: 'nav.teamsTooltip', onClick: () => teamsStore.toggleTeamsPanel() },
```

- [ ] **Step 4: Add Teams badge display in toolbar**

In the `v-for="action in headerActions"` template loop (~line 31-41), add a badge condition inside the button:
```html
<span v-if="action.id === 'teams' && teamsStore.runningAgentCount > 0" class="teams-badge">
  {{ teamsStore.runningAgentCount }}
</span>
```

- [ ] **Step 5: Add workflow event handling in WebSocket onMessage**

In the `ws.onmessage` handler (~line 731), add a case before the `error` handler (~line 968) as `else if`:
```typescript
// Before the final else if (message.type === 'error') block
else if (message.type?.startsWith('workflow_')) {
  teamsStore.handleWorkflowEvent(message.type, message)
}
```

- [ ] **Step 6: Wrap `<main>` in a flex container for split layout**

Wrap the existing `<main class="main">` element (lines 149-187) in a `<div class="chat-pane">`. The `.chat-pane` div is always present; when Teams is off it acts as a transparent pass-through, when Teams is on it becomes a flex row. No template duplication needed.

**Before** (current):
```html
<main class="main" @dragenter.prevent="..." ...>
  <div class="chat-content">...</div>
</main>
```

**After**:
```html
<div class="chat-pane">
  <main class="main" @dragenter.prevent="..." ...>
    <div class="chat-content">...</div>
  </main>
  <TeamsDivider v-if="teamsStore.teamsPanelOpen" v-model="teamsStore.splitRatio" />
  <div v-if="teamsStore.teamsPanelOpen" class="sub-agents-wrapper">
    <SubAgentPanel />
  </div>
</div>
```

- [ ] **Step 7: Add CSS for split layout**

Add to `<style scoped>`:
```css
.chat-pane {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-width: 0;
}
/* When Teams is off, main fills all space. When Teams is on, main gets its ratio from inline style. */
.main {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-width: 200px;
}
.sub-agents-wrapper {
  display: flex;
  flex-direction: column;
  min-width: 200px;
  border-left: 1px solid var(--border-color, #222);
  overflow: hidden;
}
.teams-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  font-size: 9px;
  background: var(--accent-color, #7c3aed);
  color: white;
  padding: 0 4px;
  border-radius: 8px;
  min-width: 14px;
  text-align: center;
  line-height: 16px;
}
```

Wait — since we use `v-if` on the wrapper elements (not a class), `.main` no longer needs to be `flex: 1` by default. When Teams is active, `.main` gets its size from the `teamsStore.splitRatio` inline style. When Teams is off, the `.chat-pane` div is NOT rendered, and the original `<main class="main">` (with `flex: 1`) is rendered directly.

**Revised approach**: Keep the original `<main class="main">` and conditionally wrap it:

Actually, looking at the template again, the original structure is:
```html
<div class="main-container">
  <aside class="task-board-sidebar" v-if="showTaskBoard">...</aside>
  <main class="main">...</main>
</div>
```

The cleanest approach: change `<main class="main">` to be conditionally wrapped:
```html
<div class="main-container">
  <aside class="task-board-sidebar" v-if="showTaskBoard">...</aside>
  <div class="chat-pane">
    <main class="main" :style="teamsStore.teamsPanelOpen ? { flex: teamsStore.splitRatio } : {}">
      <!-- ALL existing chat content (lines 157-186) stays here -->
    </main>
    <TeamsDivider v-if="teamsStore.teamsPanelOpen" v-model="teamsStore.splitRatio" />
    <div v-if="teamsStore.teamsPanelOpen" class="sub-agents-wrapper">
      <SubAgentPanel />
    </div>
  </div>
</div>
```

The `.chat-pane` div is always present (no v-if), and when Teams is off, it just acts as a pass-through flex container. When Teams is on, the divider and sub-agents panel appear.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/modules/chat/ChatWindow.vue
git commit -m "feat: integrate Teams split-panel into ChatWindow"
```

---

## Task 11: Add i18n Translations

**Files:**
- Modify: `frontend/src/i18n/locales/zh-CN.json`
- Modify: `frontend/src/i18n/locales/en-US.json`

- [ ] **Step 1: Add Chinese translations**

In `zh-CN.json`, add a new top-level `"teams"` key (after `"todo"`):
```json
"teams": {
  "title": "团队",
  "running": "运行中",
  "manage": "管理",
  "createTeam": "创建团队",
  "editTeam": "编辑团队",
  "deleteTeam": "删除团队",
  "confirmDelete": "确定删除团队「{name}」？",
  "noWorkflow": "暂无运行中的工作流",
  "noWorkflowHint": "通过 @团队名 调用团队，或使用 workflow_run 工具",
  "noTeams": "暂无团队，点击上方按钮创建",
  "mode": {
    "pipeline": "Pipeline（顺序执行）",
    "graph": "Graph（DAG 依赖图）",
    "council": "Council（多角度讨论）"
  },
  "status": {
    "queued": "排队中",
    "running": "运行中",
    "waiting": "等待中",
    "completed": "已完成",
    "error": "失败"
  },
  "member": "成员",
  "agents": "{count} 成员",
  "skillInjection": "启用技能注入",
  "crossReview": "交叉审阅",
  "teamName": "团队名称",
  "orchestrationMode": "编排模式",
  "memberList": "成员列表",
  "addMember": "添加成员",
  "role": "角色",
  "task": "任务描述",
  "systemPrompt": "系统提示词",
  "perspective": "视角",
  "dependsOn": "依赖 Agent",
  "condition": "条件"
}
```

Add to `"nav"` section:
```json
"teams": "团队",
"teamsTooltip": "查看和管理多 Agent 团队"
```

- [ ] **Step 2: Add English translations**

In `en-US.json`, add:
```json
"teams": {
  "title": "Teams",
  "running": "Running",
  "manage": "Manage",
  "createTeam": "Create Team",
  "editTeam": "Edit Team",
  "deleteTeam": "Delete Team",
  "confirmDelete": "Delete team \"{name}\"?",
  "noWorkflow": "No active workflow",
  "noWorkflowHint": "Mention a team with @team_name or use workflow_run tool",
  "noTeams": "No teams yet. Click above to create one.",
  "mode": {
    "pipeline": "Pipeline (Sequential)",
    "graph": "Graph (DAG)",
    "council": "Council (Deliberation)"
  },
  "status": {
    "queued": "Queued",
    "running": "Running",
    "waiting": "Waiting",
    "completed": "Completed",
    "error": "Error"
  },
  "member": "Member",
  "agents": "{count} members",
  "skillInjection": "Enable skill injection",
  "crossReview": "Cross review",
  "teamName": "Team name",
  "orchestrationMode": "Orchestration mode",
  "memberList": "Member list",
  "addMember": "Add member",
  "role": "Role",
  "task": "Task description",
  "systemPrompt": "System prompt",
  "perspective": "Perspective",
  "dependsOn": "Depends on",
  "condition": "Condition"
}
```

Add to `"nav"` section:
```json
"teams": "Teams",
"teamsTooltip": "View and manage multi-agent teams"
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/i18n/locales/zh-CN.json frontend/src/i18n/locales/en-US.json
git commit -m "feat: add i18n translations for Teams feature"
```

---

## Task 12: End-to-End Testing

**Files:** None new — test existing integration.

- [ ] **Step 1: Verify backend starts without errors**

```bash
cd /mnt/d/code/AIE_0302/AIE
python -c "from backend.modules.agent.workflow import WorkflowEngine; print('WorkflowEngine OK')"
python -c "from backend.modules.agent.context import ContextBuilder; print('ContextBuilder OK')"
python -c "from backend.api.agent_teams import router; print('AgentTeams API OK')"
```

- [ ] **Step 2: Build frontend**

```bash
cd /mnt/d/code/AIE_0302/AIE/frontend
npm run build
```

- [ ] **Step 3: Start application and verify**

```bash
cd /mnt/d/code/AIE_0302/AIE
python start_dev.py
```

Manual verification checklist:
- [ ] Teams button appears in toolbar header
- [ ] Clicking Teams button opens/closes split panel
- [ ] Draggable divider works and ratio persists on reload
- [ ] Manage tab shows team list (or empty state)
- [ ] Create team modal works (create, edit, delete)
- [ ] Backend workflow events are emitted (trigger a workflow and check browser WS console)
- [ ] Running tab shows sub-agent slots when workflow is active
- [ ] Sub-agent slots display messages, tool calls, progress
- [ ] Right-side config panels still work alongside Teams panel
- [ ] TaskBoard still updates with workflow tasks

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete multi-agent Teams integration"
```
