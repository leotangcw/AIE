/**
 * Agent Teams API 客户端
 *
 * 提供 Agent Teams 的 CRUD 操作和模型配置管理
 */

import apiClient from './client'

// ============================================================================
// 类型定义
// ============================================================================

export interface AgentDefinition {
    id: string
    role: string
    system_prompt?: string
    task: string
    perspective?: string
    depends_on?: string[]
    condition?: any
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

// ============================================================================
// API 方法
// ============================================================================

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
