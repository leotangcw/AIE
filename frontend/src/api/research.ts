/* eslint-disable */
/* Research API Client */
import apiClient from './client'

export interface KnowledgeRef {
  source_name: string
  content: string
  file_path?: string
  score: number
}

export interface Exploration {
  id: string
  type: 'thinking' | 'action' | 'result' | 'retrieved' | 'decision'
  content: string
  metadata: Record<string, any>
  timestamp: string
}

export interface ResearchSession {
  id: string
  query: string
  session_type: 'research' | 'chat'
  start_time: string
  end_time?: string
  retrieved_knowledge: KnowledgeRef[]
  explorations: Exploration[]
  final_solution: string
  success: boolean
  auto_tagged: boolean
  need_consolidation: boolean
}

export interface ConsolidationResult {
  id: string
  session_id: string
  problem_summary: string
  solution_steps: string[]
  pitfalls: string[]
  new_knowledge: string
  skill_name?: string
  created_at: string
}

export const researchApi = {
  // 开始研究会话
  startSession: async (query: string, sessionType: 'research' | 'chat' = 'chat'): Promise<{ session_id: string }> => {
    const response = await apiClient.post('/api/research/start', {
      query,
      session_type: sessionType
    })
    return response
  },

  // 记录探索过程
  logExploration: async (
    sessionId: string,
    explorationType: string,
    content: string,
    metadata: Record<string, any> = {}
  ): Promise<void> => {
    await apiClient.post(`/api/research/${sessionId}/exploration`, {
      exploration_type: explorationType,
      content,
      metadata
    })
  },

  // 添加知识引用
  addKnowledgeRef: async (
    sessionId: string,
    knowledge: KnowledgeRef
  ): Promise<void> => {
    await apiClient.post(`/api/research/${sessionId}/knowledge`, knowledge)
  },

  // 完成会话
  completeSession: async (
    sessionId: string,
    solution: string,
    success: boolean
  ): Promise<void> => {
    await apiClient.post(`/api/research/${sessionId}/complete`, {
      solution,
      success
    })
  },

  // 获取研究历史
  getHistory: async (limit = 20): Promise<{ sessions: any[] }> => {
    const response = await apiClient.get(`/api/research/history?limit=${limit}`)
    return response
  },

  // 获取会话详情
  getSession: async (sessionId: string): Promise<ResearchSession> => {
    const response = await apiClient.get(`/api/research/${sessionId}`)
    return response
  },

  // 获取沉淀状态
  getConsolidationStatus: async (): Promise<{
    pending_sessions: number
    consolidated_solutions: number
    recent_solutions: any[]
  }> => {
    const response = await apiClient.get('/api/research/consolidation/status')
    return response
  },

  // 手动触发沉淀
  consolidate: async (sessionId?: string): Promise<{
    success: boolean
    consolidated: number
    results: ConsolidationResult[]
  }> => {
    const url = sessionId
      ? `/api/research/consolidate?session_id=${sessionId}`
      : '/api/research/consolidate'
    const response = await apiClient.post(url)
    return response
  },

  // 获取已沉淀的解决方案
  getSolutions: async (limit = 20): Promise<{ solutions: ConsolidationResult[] }> => {
    const response = await apiClient.get(`/api/research/solutions?limit=${limit}`)
    return response
  },
}

export default researchApi
