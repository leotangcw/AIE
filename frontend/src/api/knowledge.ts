/* eslint-disable */
/* Knowledge API Client */
import apiClient from './client'

export interface KnowledgeSource {
  id: string
  name: string
  source_type: string
  enabled: boolean
  created_at: string
  last_sync: string | null
}

export interface KnowledgeChunk {
  id: string
  source_id: string
  content: string
  metadata: Record<string, any>
}

export interface RetrieveRequest {
  query: string
  top_k?: number
  source_ids?: string[]
}

export interface KnowledgeRetrieveResult {
  results: KnowledgeChunk[]
  count: number
}

export const knowledgeApi = {
  // 获取所有知识源
  getSources: async (): Promise<KnowledgeSource[]> => {
    const response = await apiClient.get('/api/knowledge/sources')
    return response || []
  },

  // 创建知识源
  createSource: async (name: string, sourceType: string, config: Record<string, any> = {}): Promise<KnowledgeSource> => {
    const response = await apiClient.post('/api/knowledge/sources', {
      name,
      source_type: sourceType,
      config
    })
    return response
  },

  // 删除知识源
  deleteSource: async (sourceId: string): Promise<void> => {
    await apiClient.delete(`/api/knowledge/sources/${sourceId}`)
  },

  // 上传文档到知识源
  addDocument: async (sourceId: string, file: File): Promise<{ chunks_added: number }> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.postForm(`/api/knowledge/sources/${sourceId}/documents`, formData)
    return response
  },

  // 检索知识
  retrieve: async (request: RetrieveRequest): Promise<KnowledgeRetrieveResult> => {
    const response = await apiClient.post('/api/knowledge/retrieve', request)
    return response
  },

  // 增强上下文
  augmentContext: async (query: string, context: Record<string, any>, topK = 3): Promise<Record<string, any>> => {
    const response = await apiClient.post('/api/knowledge/augment', {
      query,
      context,
      top_k: topK
    })
    return response
  },
}

export default knowledgeApi
