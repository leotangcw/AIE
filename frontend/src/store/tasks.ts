/**
 * TaskBoard Pinia Store
 *
 * 管理 TaskBoard 的响应式状态，通过 WebSocket 事件驱动更新。
 * 替代 TaskBoard.vue 内的本地状态和轮询逻辑。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { taskBoardAPI, type TaskItem } from '@/api/endpoints'

export const useTaskStore = defineStore('tasks', () => {
  // State
  const systemTasks = ref<TaskItem[]>([])
  const runningTasks = ref<TaskItem[]>([])
  const doneTasks = ref<TaskItem[]>([])
  const loading = ref(false)
  const modelStatus = ref<Record<string, any>>({})

  // Computed
  const hasRunningTasks = computed(() => runningTasks.value.length > 0)

  // HTTP 初始加载
  async function loadTasks(sessionId: string | null) {
    if (loading.value) return
    loading.value = true

    try {
      const systemRes = await taskBoardAPI.getSystemTasks()
      systemTasks.value = Array.isArray(systemRes) ? systemRes : (systemRes.tasks || [])

      if (sessionId) {
        const sessionRes = await taskBoardAPI.getSessionTasks(sessionId)
        runningTasks.value = sessionRes.running_tasks || []
        doneTasks.value = sessionRes.done_tasks || []
      } else {
        runningTasks.value = []
        doneTasks.value = []
      }
    } catch (e) {
      console.error('Failed to load tasks:', e)
    } finally {
      loading.value = false
    }
  }

  // WebSocket 事件处理

  function addTask(taskId: string, label: string) {
    // 检查是否已存在
    if (runningTasks.value.some(t => t.id === taskId)) return
    runningTasks.value.unshift({
      id: taskId,
      title: label,
      description: '',
      task_scope: 'session',
      session_id: null,
      task_type: 'subagent',
      parent_id: null,
      cron_id: null,
      cron_expression: null,
      next_run_at: null,
      last_run_status: null,
      last_run_at: null,
      status: 'running',
      progress: 0,
      started_at: new Date().toISOString(),
      completed_at: null,
      estimated_duration: null,
      actual_duration: null,
      error_message: null,
      retry_count: 0,
      max_retries: 3,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
  }

  function updateTaskProgress(taskId: string, progress: number, message?: string) {
    const task = runningTasks.value.find(t => t.id === taskId)
    if (task) {
      task.progress = Math.min(100, Math.max(0, progress))
      if (message) {
        // 更新描述信息（保留原始描述，追加进度）
        const prefix = '[进度]'
        const existing = (task.description || '')
        const idx = existing.indexOf(prefix)
        if (idx >= 0) {
          task.description = existing.substring(0, idx) + `${prefix} ${message}`
        } else {
          task.description = existing + (existing ? '\n' : '') + `${prefix} ${message}`
        }
      }
    }
  }

  function updateTaskAnalysis(taskId: string, data: {
    progress: number
    summary: string
    elapsed_minutes: number
    wake_count: number
  }) {
    const task = runningTasks.value.find(t => t.id === taskId)
    if (task) {
      task.progress = Math.min(100, Math.max(0, data.progress))
      // Update description with latest analysis
      if (data.summary) {
        const prefix = '[分析]'
        const existing = (task.description || '')
        const idx = existing.indexOf(prefix)
        if (idx >= 0) {
          task.description = existing.substring(0, idx) + `${prefix} ${data.summary}`
        } else {
          task.description = existing + (existing ? '\n' : '') + `${prefix} ${data.summary}`
        }
      }
    }
  }

  function updateModelStatus(models: Record<string, any>) {
    modelStatus.value = models
  }

  function completeTask(taskId: string, result?: string) {
    const index = runningTasks.value.findIndex(t => t.id === taskId)
    if (index !== -1) {
      const [task] = runningTasks.value.splice(index, 1)
      task.status = 'done'
      task.progress = 100
      task.completed_at = new Date().toISOString()
      if (result) {
        const prefix = '[结果]'
        const existing = (task.description || '')
        task.description = existing + (existing ? '\n' : '') + `${prefix} ${result.substring(0, 200)}`
      }
      doneTasks.value.unshift(task)
      // 限制已完成列表数量
      if (doneTasks.value.length > 20) {
        doneTasks.value = doneTasks.value.slice(0, 20)
      }
    }
  }

  function failTask(taskId: string, error: string) {
    const index = runningTasks.value.findIndex(t => t.id === taskId)
    if (index !== -1) {
      const [task] = runningTasks.value.splice(index, 1)
      task.status = 'failed'
      task.completed_at = new Date().toISOString()
      task.error_message = error
      doneTasks.value.unshift(task)
    }
  }

  function updateTaskStatus(taskId: string, status: string, progress?: number) {
    if (status === 'done' || status === 'completed') {
      completeTask(taskId)
      return
    }
    if (status === 'failed') {
      failTask(taskId, '任务失败')
      return
    }

    const task = runningTasks.value.find(t => t.id === taskId)
    if (task) {
      task.status = status
      if (progress !== undefined) {
        task.progress = Math.min(100, Math.max(0, progress))
      }
    }
  }

  // 从 HTTP 响应刷新任务列表（兜底轮调用）
  async function refreshFromServer(sessionId: string | null) {
    if (!sessionId) return
    try {
      const sessionRes = await taskBoardAPI.getSessionTasks(sessionId)
      runningTasks.value = sessionRes.running_tasks || []
      doneTasks.value = sessionRes.done_tasks || []
    } catch {
      // 静默失败
    }
  }

  return {
    systemTasks,
    runningTasks,
    doneTasks,
    loading,
    hasRunningTasks,
    modelStatus,
    loadTasks,
    addTask,
    updateTaskProgress,
    updateTaskAnalysis,
    completeTask,
    failTask,
    updateTaskStatus,
    updateModelStatus,
    refreshFromServer,
  }
})
