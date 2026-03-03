// 经验学习 API 客户端
import apiClient from './client'

export interface LearnedSkill {
  id: string
  name: string
  description: string
  trigger_conditions: string[]
  action_steps: string[]
  confidence: number
  source: string
  usage_count: number
}

export interface LearnRequest {
  task_description: string
  user_feedback: string
  original_output: string
  final_output: string
  context?: Record<string, any>
}

export const experienceAPI = {
  // 获取所有技能
  async getSkills(minConfidence: number = 0): Promise<LearnedSkill[]> {
    const response = await apiClient.get(`/api/experience/skills?min_confidence=${minConfidence}`)
    return response.data
  },

  // 获取单个技能
  async getSkill(skillId: string): Promise<LearnedSkill> {
    const response = await apiClient.get(`/api/experience/skills/${skillId}`)
    return response.data
  },

  // 从反馈学习
  async learn(request: LearnRequest): Promise<LearnedSkill> {
    const response = await apiClient.post('/api/experience/learn', request)
    return response.data
  },

  // 应用技能
  async applySkill(skillId: string): Promise<void> {
    await apiClient.post(`/api/experience/skills/${skillId}/apply`)
  },

  // 更新置信度
  async updateConfidence(skillId: string, delta: number): Promise<void> {
    await apiClient.post(`/api/experience/skills/${skillId}/confidence`, null, {
      params: { delta }
    })
  },

  // 导出技能
  async exportSkills(): Promise<{ skills: any[] }> {
    const response = await apiClient.get('/api/experience/export')
    return response.data
  },
}
