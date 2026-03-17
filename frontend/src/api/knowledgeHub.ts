/* eslint-disable */
/* KnowledgeHub API Client */

import apiClient from './client'

export interface LLMConfig {
  enabled: boolean
  model: string
  api_key: string
  base_url: string
  temperature: number
  max_tokens: number
  prompt_style: string
}

export interface CacheConfig {
  enabled: boolean
  ttl: number
  max_memory_items: number
}

export interface SourceConfig {
  id: string
  name: string
  source_type: string
  enabled: boolean
  priority: number
  config: Record<string, any>
}

export interface KnowledgeHubConfig {
  enabled: boolean
  default_mode: 'direct' | 'llm' | 'hybrid'
  llm: LLMConfig
  cache: CacheConfig
  sources: SourceConfig[]
  storage_dir: string
}

export interface RetrieveRequest {
  query: string
  mode?: 'direct' | 'llm' | 'hybrid'
  top_k?: number
  source_ids?: string[]
}

export interface RetrieveResult {
  content: string
  sources: Array<{
    content: string
    source: string
  }>
  mode: string
  processing_time: number
  llm_used: boolean
}

export const knowledgeHubApi = {
  // 知识检索
  retrieve: async (request: RetrieveRequest): Promise<RetrieveResult> => {
    const response = await apiClient.post('/api/knowledge_hub/retrieve', request)
    return response.data
  },

  // 智能数据库查询
  queryDb: async (question: string): Promise<any> => {
    const response = await apiClient.post('/api/knowledge_hub/query-db', { question })
    return response.data
  },

  // 获取配置
  getConfig: async (): Promise<KnowledgeHubConfig> => {
    const response = await apiClient.get('/api/knowledge_hub/config')
    return response.data
  },

  // 更新配置
  updateConfig: async (config: Partial<KnowledgeHubConfig>): Promise<void> => {
    await apiClient.put('/api/knowledge_hub/config', config)
  },

  // 刷新缓存
  refreshCache: async (cacheType?: string): Promise<void> => {
    await apiClient.post('/api/knowledge_hub/cache/refresh', null, { params: { cache_type: cacheType } })
  },

  // 获取知识源列表
  getSources: async (): Promise<SourceConfig[]> => {
    const response = await apiClient.get('/api/knowledge_hub/sources')
    return response.data
  },

  // 创建知识源
  createSource: async (source: {
    name: string
    source_type: string
    config?: Record<string, any>
    enabled?: boolean
    priority?: number
  }): Promise<SourceConfig> => {
    const response = await apiClient.post('/api/knowledge_hub/sources', source)
    return response.data
  },

  // 同步知识源
  syncSource: async (sourceId: string): Promise<{ chunks_count: number }> => {
    const response = await apiClient.post(`/api/knowledge_hub/sources/${sourceId}/sync`)
    return response.data
  },
}

export default knowledgeHubApi
