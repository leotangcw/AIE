/**
 * 经验学习 Store
 *
 * Experience Learning Store
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import apiClient from '@/api/client'

export interface Experience {
  id: string
  name: string
  description: string
  category: string
  content: string
  skill_name?: string
  trigger_keywords: string[]
  feedback_count: number
  positive_count: number
  negative_count: number
  created_at: string
  updated_at: string
}

export interface ExperienceStats {
  total: number
  by_category: Record<string, number>
  total_feedback: number
}

export const useExperienceStore = defineStore('experience', () => {
  // 状态
  const experiences: Ref<Experience[]> = ref([])
  const stats: Ref<ExperienceStats | null> = ref(null)
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)

  // 计算属性
  const categories = computed(() => {
    const cats = new Set(experiences.value.map(e => e.category))
    return Array.from(cats)
  })

  const totalExperiences = computed(() => experiences.value.length)

  // 方法
  async function fetchExperiences() {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.get('/api/experience/')
      experiences.value = response.experiences || []
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch experiences'
      console.error('Failed to fetch experiences:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await apiClient.get('/api/experience/stats')
      stats.value = response
    } catch (e: any) {
      console.error('Failed to fetch experience stats:', e)
    }
  }

  async function createExperience(data: {
    name: string
    description: string
    category: string
    content: string
    skill_name?: string
    trigger_keywords?: string[]
  }) {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.post('/api/experience/', data)
      experiences.value.push(response)
      return response
    } catch (e: any) {
      error.value = e.message || 'Failed to create experience'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateExperience(id: string, data: Partial<{
    name: string
    description: string
    category: string
    content: string
    skill_name: string
    trigger_keywords: string[]
  }>) {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.put(`/api/experience/${id}`, data)
      const index = experiences.value.findIndex(e => e.id === id)
      if (index !== -1) {
        experiences.value[index] = response
      }
      return response
    } catch (e: any) {
      error.value = e.message || 'Failed to update experience'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteExperience(id: string) {
    loading.value = true
    error.value = null

    try {
      await apiClient.delete(`/api/experience/${id}`)
      experiences.value = experiences.value.filter(e => e.id !== id)
    } catch (e: any) {
      error.value = e.message || 'Failed to delete experience'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function submitFeedback(id: string, is_positive: boolean) {
    try {
      const response = await apiClient.post(`/api/experience/${id}/feedback`, {
        is_positive
      })
      // 更新本地状态
      const exp = experiences.value.find(e => e.id === id)
      if (exp) {
        exp.feedback_count++
        if (is_positive) {
          exp.positive_count++
        } else {
          exp.negative_count++
        }
      }
      return response
    } catch (e: any) {
      console.error('Failed to submit feedback:', e)
      throw e
    }
  }

  async function applyExperience(id: string, context: Record<string, any>) {
    try {
      const response = await apiClient.post(`/api/experience/${id}/apply`, context)
      return response
    } catch (e: any) {
      console.error('Failed to apply experience:', e)
      throw e
    }
  }

  return {
    // 状态
    experiences,
    stats,
    loading,
    error,

    // 计算属性
    categories,
    totalExperiences,

    // 方法
    fetchExperiences,
    fetchStats,
    createExperience,
    updateExperience,
    deleteExperience,
    submitFeedback,
    applyExperience,
  }
})
