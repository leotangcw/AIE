/* eslint-disable */
/* Security API Client - Advanced Data Security Features */
import apiClient from './client'

export interface DataClassification {
  id: string
  level: 'public' | 'internal' | 'confidential' | 'secret'
  owner: string
  description: string
  tags: string[]
  created_at: string
}

export interface AieSecurityProfile {
  aie_id: string
  level: 'public' | 'internal' | 'confidential' | 'secret'
  permissions: string[]
  allowed_data_ids: string[]
  denied_data_ids: string[]
}

export interface ClassificationCreate {
  data_id: string
  level: string
  owner: string
  description?: string
  tags?: string[]
}

export interface ProfileCreate {
  aie_id: string
  level: string
  permissions?: string[]
  allowed_data_ids?: string[]
  denied_data_ids?: string[]
}

export const securityApi = {
  // 获取安全配置
  getConfig: async (): Promise<{ enabled: boolean }> => {
    const response = await apiClient.get('/api/security/config')
    return response
  },

  // 设置安全配置
  setConfig: async (enabled: boolean): Promise<void> => {
    await apiClient.post('/api/security/config', { enabled })
  },

  // 获取所有数据分类
  getClassifications: async (): Promise<DataClassification[]> => {
    const response = await apiClient.get('/api/security/classifications')
    return response || []
  },

  // 创建数据分类
  createClassification: async (data: ClassificationCreate): Promise<DataClassification> => {
    const response = await apiClient.post('/api/security/classifications', data)
    return response
  },

  // 删除数据分类
  deleteClassification: async (dataId: string): Promise<void> => {
    await apiClient.delete(`/api/security/classifications/${dataId}`)
  },

  // 获取所有 AIE 配置
  getProfiles: async (): Promise<AieSecurityProfile[]> => {
    const response = await apiClient.get('/api/security/profiles')
    return response || []
  },

  // 创建 AIE 配置
  createProfile: async (data: ProfileCreate): Promise<AieSecurityProfile> => {
    const response = await apiClient.post('/api/security/profiles', data)
    return response
  },

  // 删除 AIE 配置
  deleteProfile: async (aieId: string): Promise<void> => {
    await apiClient.delete(`/api/security/profiles/${aieId}`)
  },

  // 检查访问权限
  checkAccess: async (aieId: string, dataId: string): Promise<{ allowed: boolean }> => {
    const response = await apiClient.post('/api/security/check-access', { aie_id: aieId, data_id: dataId })
    return response
  },

  // 过滤可访问的数据
  filterAccess: async (aieId: string, dataIds: string[]): Promise<{ allowed_ids: string[]; total: number; allowed: number }> => {
    const response = await apiClient.post('/api/security/filter-access', { aie_id: aieId, data_ids: dataIds })
    return response
  },
}

export default securityApi
