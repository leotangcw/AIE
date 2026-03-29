// SuperWorkers 轨迹与技能进化 API 客户端
import apiClient from './client'

// ── 类型定义 ──

export interface TraceStats {
  total: number
  success_count: number
  success_rate: number
  with_knowledge: number
  knowledge_rate: number
  avg_duration: number
  avg_tool_calls: number
}

export interface TraceSummary {
  trace_id: string
  session_id: string
  started_at: string
  ended_at: string
  task_type: string
  outcome: string
  has_knowledge: number
  tool_calls_count: number
  total_duration_ms: number
}

export interface TraceDetail extends TraceSummary {
  input: { user_message: string; channel: string }
  execution: { iterations: any[]; tool_calls: TraceToolCall[] }
  knowledge_stage: {
    local_skills_checked: any[]
    local_skills_used: string[]
    enterprise_knowledge_queried: boolean
    knowledge_results: { query: string; result_preview: string; mode: string }[]
  }
  output: { outcome: string; tool_calls_count: number }
  metadata: { model: string; task_type: string; total_duration_ms: number; plugin_active: string }
}

export interface TraceToolCall {
  tool: string
  arguments: Record<string, any>
  called_at: string
  duration_ms: number | null
  success: boolean | null
  result_summary: string | null
}

export interface SkillMeta {
  name: string
  title: string
  description: string
  confidence: number
  created: string
  status: string
}

export interface CandidateSkillDetail {
  name: string
  content: string
}

// ── API 方法 ──

export const experienceAPI = {
  // 获取轨迹统计
  async getTraceStats(days: number = 30): Promise<TraceStats> {
    const response = await apiClient.get('/api/traces/stats', { params: { days } })
    return response.data
  },

  // 获取最近轨迹列表
  async getTraces(params: {
    limit?: number
    task_type?: string
    outcome?: string
  } = {}): Promise<TraceSummary[]> {
    const response = await apiClient.get('/api/traces', { params })
    return response.data
  },

  // 获取轨迹详情
  async getTraceDetail(traceId: string): Promise<TraceDetail> {
    const response = await apiClient.get(`/api/traces/${traceId}`)
    return response.data
  },

  // 从轨迹提炼候选技能
  async distillSkills(): Promise<{ message: string }> {
    const response = await apiClient.post('/api/traces/distill')
    return response.data
  },

  // 获取候选技能列表
  async getCandidateSkills(): Promise<SkillMeta[]> {
    const response = await apiClient.get('/api/traces/skills/candidates')
    return response.data
  },

  // 获取候选技能详情
  async getCandidateSkillDetail(name: string): Promise<CandidateSkillDetail> {
    const response = await apiClient.get(`/api/traces/skills/candidates/${name}`)
    return response.data
  },

  // 发布候选技能
  async promoteCandidateSkill(name: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post(`/api/traces/skills/candidates/${name}/promote`)
    return response.data
  },

  // 拒绝候选技能
  async rejectCandidateSkill(name: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post(`/api/traces/skills/candidates/${name}/reject`)
    return response.data
  },

  // 获取正式技能列表
  async getSkills(): Promise<SkillMeta[]> {
    const response = await apiClient.get('/api/traces/skills')
    return response.data
  },
}
