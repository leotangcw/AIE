/* eslint-disable */
/* Rules API Client */
import apiClient from './client'

export interface Rule {
  id: string
  name: string
  description: string
  condition: string
  action: string
  enabled: boolean
  priority: number
  created_at: string
  updated_at: string
}

export interface RuleCreate {
  name: string
  description: string
  condition: string
  action: string
  enabled?: boolean
  priority?: number
}

export const rulesApi = {
  // 获取所有规则
  getRules: async (): Promise<Rule[]> => {
    const response = await apiClient.get('/api/rules/')
    return response.rules || []
  },

  // 获取规则详情
  getRule: async (id: string): Promise<Rule> => {
    const response = await apiClient.get(`/api/rules/${id}`)
    return response
  },

  // 创建规则
  createRule: async (rule: RuleCreate): Promise<Rule> => {
    const response = await apiClient.post('/api/rules/', rule)
    return response
  },

  // 更新规则
  updateRule: async (id: string, rule: Partial<RuleCreate>): Promise<Rule> => {
    const response = await apiClient.put(`/api/rules/${id}`, rule)
    return response
  },

  // 删除规则
  deleteRule: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/rules/${id}`)
  },

  // 启用/禁用规则
  toggleRule: async (id: string, enabled: boolean): Promise<void> => {
    await apiClient.post(`/api/rules/${id}/toggle`, { enabled })
  },

  // 手动触发规则执行
  triggerRule: async (id: string, context: Record<string, unknown>): Promise<void> => {
    await apiClient.post(`/api/rules/${id}/trigger`, context)
  },

  // 获取规则执行历史
  getHistory: async (ruleId?: string, limit = 50): Promise<any[]> => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (ruleId) {
      params.append('rule_id', ruleId)
    }
    const response = await apiClient.get(`/api/rules/history?${params}`)
    return response.history || []
  },

  // 测试规则条件
  testCondition: async (condition: string, testContext: Record<string, unknown>): Promise<{ matches: boolean; result: any }> => {
    const response = await apiClient.post('/api/rules/test', {
      condition,
      context: testContext
    })
    return response
  },
}

export default rulesApi
