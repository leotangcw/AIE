/**
 * Teams Pinia Store
 *
 * 管理 Agent Teams 的响应式状态，包括工作流实时监控和团队 CRUD 操作。
 * 通过 WebSocket 事件驱动工作流状态更新。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
    agentTeamsAPI,
    type AgentTeamResponse,
    type AgentTeamCreateRequest,
    type AgentTeamUpdateRequest,
    type TeamModelConfig,
} from '@/api/agentTeams'

// ============================================================================
// 类型定义
// ============================================================================

export interface SubAgentMessage {
    role: 'user' | 'assistant' | 'tool'
    content: string
    tool_name?: string
    tool_result?: string
    arguments?: Record<string, any>
    is_thinking?: boolean
    timestamp?: string
}

export interface SubAgentState {
    agent_id: string
    role: string
    task: string
    status: 'queued' | 'running' | 'waiting' | 'completed' | 'error'
    progress: number
    tool_count: number
    tool_name: string
    messages: SubAgentMessage[]
    duration: number
    started_at: string | null
    completed_at: string | null
    error: string | null
}

export interface WorkflowState {
    team_name: string
    mode: string
    agents: SubAgentState[]
    started_at: string | null
    completed_at: string | null
    error: string | null
}

// ============================================================================
// Store
// ============================================================================

export const useTeamsStore = defineStore('teams', () => {
    // ---------------------------------------------------------------------------
    // State
    // ---------------------------------------------------------------------------
    const teamsPanelOpen = ref(false)
    const activeTab = ref<'running' | 'manage'>('running')
    const currentWorkflow = ref<WorkflowState | null>(null)
    const teams = ref<AgentTeamResponse[]>([])
    const splitRatio = ref(0.45)
    const loading = ref(false)
    const pendingChatInput = ref('')

    // ---------------------------------------------------------------------------
    // Computed
    // ---------------------------------------------------------------------------
    const isWorkflowActive = computed(() => {
        if (!currentWorkflow.value) return false
        if (currentWorkflow.value.completed_at) return false
        if (currentWorkflow.value.error) return false
        return true
    })

    const runningAgentCount = computed(() => {
        if (!currentWorkflow.value) return 0
        return currentWorkflow.value.agents.filter(
            a => a.status === 'running' || a.status === 'waiting'
        ).length
    })

    // ---------------------------------------------------------------------------
    // Workflow Event Handlers
    // ---------------------------------------------------------------------------

    function handleWorkflowStart(data: any) {
        const agents: SubAgentState[] = (data.agents || []).map((a: any) => ({
            agent_id: a.agent_id || a.id,
            role: a.role || '',
            task: a.task || '',
            status: 'queued' as const,
            progress: 0,
            tool_count: 0,
            tool_name: '',
            messages: [],
            duration: 0,
            started_at: null,
            completed_at: null,
            error: null,
        }))

        currentWorkflow.value = {
            team_name: data.team_name || data.name || 'Team',
            mode: data.mode || 'pipeline',
            agents,
            started_at: data.started_at || new Date().toISOString(),
            completed_at: null,
            error: null,
        }

        // Auto-open panel when workflow starts
        openTeamsPanel()
        activeTab.value = 'running'
    }

    function handleWorkflowAgentStart(data: any) {
        if (!currentWorkflow.value) return
        const agent = findAgent(data.agent_id)
        if (!agent) return
        agent.status = 'running'
        agent.started_at = data.started_at || new Date().toISOString()
    }

    function handleWorkflowAgentToolCall(data: any) {
        if (!currentWorkflow.value) return
        const agent = findAgent(data.agent_id)
        if (!agent) return
        agent.tool_count++
        agent.tool_name = data.tool || data.tool_name || ''
        agent.messages.push({
            role: 'tool',
            content: data.input || data.content || '',
            tool_name: data.tool || data.tool_name || '',
            arguments: data.arguments || {},
            timestamp: new Date().toISOString(),
        })
    }

    function handleWorkflowAgentToolResult(data: any) {
        if (!currentWorkflow.value) return
        const agent = findAgent(data.agent_id)
        if (!agent) return
        // Update the last tool message's tool_result
        for (let i = agent.messages.length - 1; i >= 0; i--) {
            if (agent.messages[i].role === 'tool') {
                agent.messages[i].tool_result = data.result || data.output || ''
                break
            }
        }
    }

    function handleWorkflowAgentChunk(data: any) {
        if (!currentWorkflow.value) return
        const agent = findAgent(data.agent_id)
        if (!agent) return
        const content = data.chunk || data.content || ''
        if (!content) return
        // Append to last assistant message, or create new one
        const lastMsg = agent.messages[agent.messages.length - 1]
        if (lastMsg && lastMsg.role === 'assistant' && !lastMsg.is_thinking) {
            lastMsg.content += content
        } else {
            agent.messages.push({
                role: 'assistant',
                content,
                is_thinking: false,
                timestamp: new Date().toISOString(),
            })
        }
    }

    function handleWorkflowAgentProgress(data: any) {
        if (!currentWorkflow.value) return
        const agent = findAgent(data.agent_id)
        if (!agent) return
        if (data.progress !== undefined) {
            agent.progress = data.progress
        }
        if (data.status !== undefined) {
            agent.status = data.status
        }
    }

    function handleWorkflowAgentComplete(data: any) {
        if (!currentWorkflow.value) return
        const agent = findAgent(data.agent_id)
        if (!agent) return
        agent.status = 'completed'
        agent.completed_at = data.completed_at || new Date().toISOString()
        // Calculate duration
        if (agent.started_at) {
            agent.duration = (new Date(agent.completed_at).getTime() - new Date(agent.started_at).getTime()) / 1000
        }
        agent.messages.push({
            role: 'assistant',
            content: data.result || data.content || 'Completed',
            timestamp: new Date().toISOString(),
        })
    }

    function handleWorkflowComplete(data: any) {
        if (!currentWorkflow.value) return
        currentWorkflow.value.completed_at = data.completed_at || new Date().toISOString()
        // Mark any remaining agents as completed
        for (const agent of currentWorkflow.value.agents) {
            if (agent.status === 'running' || agent.status === 'waiting' || agent.status === 'queued') {
                agent.status = 'completed'
                agent.completed_at = currentWorkflow.value.completed_at
                if (agent.started_at) {
                    agent.duration = (new Date(agent.completed_at).getTime() - new Date(agent.started_at).getTime()) / 1000
                }
            }
        }
    }

    function handleWorkflowError(data: any) {
        if (!currentWorkflow.value) return
        currentWorkflow.value.error = data.error || data.message || 'Unknown error'
        // Mark the specific agent as error if provided
        if (data.agent_id) {
            const agent = findAgent(data.agent_id)
            if (agent) {
                agent.status = 'error'
                agent.error = currentWorkflow.value.error
                agent.completed_at = new Date().toISOString()
                if (agent.started_at) {
                    agent.duration = (new Date(agent.completed_at).getTime() - new Date(agent.started_at).getTime()) / 1000
                }
            }
        }
    }

    function handleWorkflowEvent(type: string, data: any) {
        switch (type) {
            case 'workflow_start':
                handleWorkflowStart(data)
                break
            case 'workflow_agent_start':
                handleWorkflowAgentStart(data)
                break
            case 'workflow_agent_tool_call':
                handleWorkflowAgentToolCall(data)
                break
            case 'workflow_agent_tool_result':
                handleWorkflowAgentToolResult(data)
                break
            case 'workflow_agent_chunk':
                handleWorkflowAgentChunk(data)
                break
            case 'workflow_agent_progress':
                handleWorkflowAgentProgress(data)
                break
            case 'workflow_agent_complete':
                handleWorkflowAgentComplete(data)
                break
            case 'workflow_complete':
                handleWorkflowComplete(data)
                break
            case 'workflow_error':
                handleWorkflowError(data)
                break
            default:
                // Unknown event type - ignore
                break
        }
    }

    // ---------------------------------------------------------------------------
    // Helper
    // ---------------------------------------------------------------------------

    function findAgent(agentId: string): SubAgentState | undefined {
        return currentWorkflow.value?.agents.find(a => a.agent_id === agentId)
    }

    // ---------------------------------------------------------------------------
    // Panel Management
    // ---------------------------------------------------------------------------

    function requestChatInput(text: string) {
        pendingChatInput.value = text
        activeTab.value = 'running'
    }

    function consumeChatInput(): string {
        const val = pendingChatInput.value
        pendingChatInput.value = ''
        return val
    }

    function toggleTeamsPanel() {
        teamsPanelOpen.value = !teamsPanelOpen.value
    }

    function openTeamsPanel() {
        teamsPanelOpen.value = true
    }

    function closeTeamsPanel() {
        teamsPanelOpen.value = false
    }

    // ---------------------------------------------------------------------------
    // Team CRUD
    // ---------------------------------------------------------------------------

    async function fetchTeams() {
        try {
            const result = await agentTeamsAPI.list()
            teams.value = Array.isArray(result) ? result : []
        } catch (e) {
            console.error('Failed to fetch teams:', e)
        }
    }

    async function createTeam(data: AgentTeamCreateRequest): Promise<AgentTeamResponse | null> {
        try {
            const team = await agentTeamsAPI.create(data)
            teams.value.push(team)
            return team
        } catch (e) {
            console.error('Failed to create team:', e)
            return null
        }
    }

    async function updateTeam(id: string, data: AgentTeamUpdateRequest): Promise<AgentTeamResponse | null> {
        try {
            const team = await agentTeamsAPI.update(id, data)
            const idx = teams.value.findIndex(t => t.id === id)
            if (idx !== -1) {
                teams.value[idx] = team
            }
            return team
        } catch (e) {
            console.error('Failed to update team:', e)
            return null
        }
    }

    async function deleteTeam(id: string): Promise<boolean> {
        try {
            await agentTeamsAPI.delete(id)
            teams.value = teams.value.filter(t => t.id !== id)
            return true
        } catch (e) {
            console.error('Failed to delete team:', e)
            return false
        }
    }

    async function toggleTeamActive(id: string): Promise<boolean> {
        const team = teams.value.find(t => t.id === id)
        if (!team) return false
        return updateTeam(id, { is_active: !team.is_active }).then(t => !!t)
    }

    async function getTeamConfig(id: string) {
        try {
            return await agentTeamsAPI.getConfig(id)
        } catch (e) {
            console.error('Failed to get team config:', e)
            return null
        }
    }

    async function updateTeamConfig(id: string, data: TeamModelConfig) {
        try {
            return await agentTeamsAPI.updateConfig(id, data)
        } catch (e) {
            console.error('Failed to update team config:', e)
            return null
        }
    }

    async function resetTeamConfig(id: string) {
        try {
            return await agentTeamsAPI.resetConfig(id)
        } catch (e) {
            console.error('Failed to reset team config:', e)
            return null
        }
    }

    // ---------------------------------------------------------------------------
    // Init
    // ---------------------------------------------------------------------------

    function init() {
        // Restore split ratio from localStorage
        const saved = localStorage.getItem('aie-teams-split-ratio')
        if (saved) {
            const parsed = parseFloat(saved)
            if (!isNaN(parsed) && parsed > 0.1 && parsed < 0.9) {
                splitRatio.value = parsed
            }
        }
        fetchTeams()
    }

    // ---------------------------------------------------------------------------
    // Return
    // ---------------------------------------------------------------------------

    return {
        // State
        teamsPanelOpen,
        activeTab,
        currentWorkflow,
        teams,
        splitRatio,
        loading,
        pendingChatInput,

        // Computed
        isWorkflowActive,
        runningAgentCount,

        // Workflow Event Handlers
        handleWorkflowEvent,

        // Panel Management
        toggleTeamsPanel,
        openTeamsPanel,
        closeTeamsPanel,
        requestChatInput,
        consumeChatInput,

        // Team CRUD
        fetchTeams,
        createTeam,
        updateTeam,
        deleteTeam,
        toggleTeamActive,
        getTeamConfig,
        updateTeamConfig,
        resetTeamConfig,

        // Init
        init,
    }
})
