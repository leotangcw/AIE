/* eslint-disable */
/* KnowledgeHub API Client */

import apiClient from './client'
import { RetrievalMode, PromptStyle, SourceType } from '@/types/knowledge'

// =====================
// Config Types
// =====================

export interface LLMConfig {
  enabled: boolean
  model: string
  api_key: string
  base_url: string
  temperature: number
  max_tokens: number
  prompt_style: PromptStyle
}

export interface CacheConfig {
  enabled: boolean
  ttl: number
  max_memory_items: number
  cache_queries: boolean
}

export interface ChunkConfig {
  strategy: 'fixed' | 'semantic' | 'parent_child' | 'recursive'
  chunk_size: number
  chunk_overlap: number
  parent_chunk_size: number
}

export interface RerankConfig {
  enabled: boolean
  semantic_weight: number
  recency_weight: number
  hotness_weight: number
  source_weight: number
}

export interface RetrievalConfig {
  mode: RetrievalMode
  top_k: number
  min_score: number
  rerank: RerankConfig
  vector_weight: number
  keyword_weight: number
}

export interface LocalSourceConfig {
  path: string
  file_types: string[]
  recursive: boolean
  chunk: ChunkConfig
}

export interface DatabaseSourceConfig {
  db_type: 'sqlite' | 'mysql' | 'postgresql' | 'mssql' | 'oracle'
  connection_string: string
  host: string
  port: number
  database: string
  username: string
  password: string
  tables: string[]
  text_columns: string[]
  read_only: boolean
}

export interface WebSearchSourceConfig {
  provider: 'brave' | 'google' | 'bing' | 'custom'
  api_key: string
  base_url: string
  max_results: number
  timeout: number
}

export interface SourceConfig {
  id: string
  name: string
  source_type: SourceType
  enabled: boolean
  priority: number
  config: Record<string, any>
  local?: LocalSourceConfig
  database?: DatabaseSourceConfig
  web_search?: WebSearchSourceConfig
  retrieval?: RetrievalConfig
  description: string
  tags: string[]
}

export interface KnowledgeHubConfig {
  enabled: boolean
  default_mode: RetrievalMode
  llm: LLMConfig
  cache: CacheConfig
  sources: SourceConfig[]
  storage_dir: string
  default_retrieval?: RetrievalConfig
  vector_store?: {
    enabled: boolean
    embedding_model: string
    dimension: number
  }
}

// =====================
// Request/Response Types
// =====================

export interface RetrieveRequest {
  query: string
  mode?: RetrievalMode
  top_k?: number
  min_score?: number
  source_ids?: string[]
  use_cache?: boolean
  rerank?: boolean
}

export interface RetrieveResult {
  content: string
  sources: Array<{
    content: string
    source: string
    score?: number
    original_score?: number
    score_breakdown?: Record<string, number>
  }>
  mode: string
  processing_time: number
  llm_used: boolean
}

export interface WebSearchRequest {
  query: string
  provider?: string
  max_results?: number
  fetch_content?: boolean
}

export interface WebSearchResult {
  title: string
  url: string
  snippet: string
  content: string
  source: string
  score: number
}

export interface KnowledgeStats {
  total_sources: number
  enabled_sources: number
  sources_by_type: Record<string, number>
  connectors_active: number
  vector_store?: Record<string, any>
}

// =====================
// API Client
// =====================

// Helper to unwrap backend response { code: 0, data: {...} }
const unwrapResponse = <T>(response: any): T => {
  // apiClient already returns response.data from interceptor
  // Backend wraps in { code: 0, data: {...} }
  if (response && typeof response === 'object' && 'data' in response) {
    return response.data as T
  }
  return response as T
}

export const knowledgeHubApi = {
  // 知识检索
  retrieve: async (request: RetrieveRequest): Promise<RetrieveResult> => {
    const response = await apiClient.post('/knowledge_hub/retrieve', request)
    return unwrapResponse<RetrieveResult>(response)
  },

  // 智能数据库查询
  queryDb: async (question: string, sourceId?: string): Promise<any> => {
    const response = await apiClient.post('/knowledge_hub/query-db', {
      question,
      source_id: sourceId
    })
    return unwrapResponse(response)
  },

  // 网络搜索
  webSearch: async (request: WebSearchRequest): Promise<WebSearchResult[]> => {
    const response = await apiClient.post('/knowledge_hub/web-search', request)
    return unwrapResponse<WebSearchResult[]>(response)
  },

  // 获取配置
  getConfig: async (): Promise<KnowledgeHubConfig> => {
    const response = await apiClient.get('/knowledge_hub/config')
    return unwrapResponse<KnowledgeHubConfig>(response)
  },

  // 更新配置
  updateConfig: async (config: Partial<KnowledgeHubConfig>): Promise<void> => {
    await apiClient.put('/knowledge_hub/config', config)
  },

  // 更新重排序配置
  updateRerankConfig: async (config: RerankConfig): Promise<void> => {
    await apiClient.put('/knowledge_hub/config/rerank', config)
  },

  // 刷新缓存
  refreshCache: async (cacheType?: string): Promise<void> => {
    await apiClient.post('/knowledge_hub/cache/refresh', null, {
      params: { cache_type: cacheType }
    })
  },

  // 获取知识源列表
  getSources: async (): Promise<SourceConfig[]> => {
    const response = await apiClient.get('/knowledge_hub/sources')
    return unwrapResponse<SourceConfig[]>(response)
  },

  // 获取单个知识源
  getSource: async (sourceId: string): Promise<SourceConfig> => {
    const response = await apiClient.get(`/knowledge_hub/sources/${sourceId}`)
    return unwrapResponse<SourceConfig>(response)
  },

  // 创建知识源
  createSource: async (source: {
    name: string
    source_type: SourceType
    config?: Record<string, any>
    local?: LocalSourceConfig
    database?: DatabaseSourceConfig
    web_search?: WebSearchSourceConfig
    retrieval?: RetrievalConfig
    enabled?: boolean
    priority?: number
    description?: string
    tags?: string[]
  }): Promise<SourceConfig> => {
    const response = await apiClient.post('/knowledge_hub/sources', source)
    return unwrapResponse<SourceConfig>(response)
  },

  // 同步知识源
  syncSource: async (sourceId: string): Promise<{ chunks_count: number }> => {
    const response = await apiClient.post(`/knowledge_hub/sources/${sourceId}/sync`)
    return unwrapResponse<{ chunks_count: number }>(response)
  },

  // 删除知识源
  deleteSource: async (sourceId: string): Promise<void> => {
    await apiClient.delete(`/knowledge_hub/sources/${sourceId}`)
  },

  // 获取统计信息
  getStats: async (): Promise<KnowledgeStats> => {
    const response = await apiClient.get('/knowledge_hub/stats')
    return unwrapResponse<KnowledgeStats>(response)
  },

  // 更新知识源
  updateSource: async (sourceId: string, updates: Partial<Pick<SourceConfig, 'enabled' | 'name' | 'priority' | 'description'>>): Promise<void> => {
    await apiClient.put(`/knowledge_hub/sources/${sourceId}`, updates)
  },

  // 上传文档到知识源
  addDocument: async (sourceId: string, file: File): Promise<{ chunks_added: number }> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.postForm(`/knowledge_hub/sources/${sourceId}/documents`, formData)
    return unwrapResponse<{ chunks_added: number }>(response)
  },

  // 浏览服务器目录
  browseDirectory: async (path: string): Promise<Array<{name: string, path: string, is_dir: boolean}>> => {
    const response = await apiClient.get('/knowledge_hub/browse-directory', { params: { path } })
    return unwrapResponse(response)
  },
}

export default knowledgeHubApi
