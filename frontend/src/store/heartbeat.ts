/**
 * Heartbeat Store - Pinia Store for Heartbeat Panel
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
    heartbeatAPI,
    type HeartbeatTask,
    type HeartbeatConfig,
    type HeartbeatMetrics,
    type HeartbeatEvent,
    type HeartbeatHistoryItem,
    type CreateHeartbeatTaskRequest,
    type UpdateHeartbeatTaskRequest,
} from '@/api/heartbeat'

export const useHeartbeatStore = defineStore('heartbeat', () => {
    // State
    const tasks = ref<HeartbeatTask[]>([])
    const config = ref<HeartbeatConfig | null>(null)
    const metrics = ref<HeartbeatMetrics | null>(null)
    const history = ref<HeartbeatHistoryItem[]>([])
    const recentEvents = ref<HeartbeatEvent[]>([])

    const loading = ref(false)
    const error = ref<string | null>(null)

    // Computed
    const enabledTasks = computed(() => tasks.value.filter(t => t.enabled))
    const runningTasks = computed(() => tasks.value.filter(t => t.status === 'running'))
    const errorTasks = computed(() => tasks.value.filter(t => t.status === 'error'))

    const contextUsagePercent = computed(() => {
        if (!metrics.value) return 0
        return Math.round((metrics.value.context_length / metrics.value.context_limit) * 100)
    })

    const lastHeartbeat = computed(() => {
        if (history.value.length === 0) return null
        return history.value[0]
    })

    // Actions
    async function loadTasks(sessionId?: string) {
        loading.value = true
        error.value = null
        try {
            tasks.value = await heartbeatAPI.getTasks(sessionId)
        } catch (err: any) {
            error.value = err.message || 'Failed to load tasks'
            console.error('Failed to load heartbeat tasks:', err)
        } finally {
            loading.value = false
        }
    }

    async function loadConfig() {
        try {
            config.value = await heartbeatAPI.getConfig()
        } catch (err: any) {
            console.error('Failed to load heartbeat config:', err)
        }
    }

    async function loadMetrics(sessionId?: string) {
        try {
            metrics.value = await heartbeatAPI.getMetrics(sessionId)
        } catch (err: any) {
            console.error('Failed to load metrics:', err)
        }
    }

    async function loadHistory(limit: number = 20, sessionId?: string) {
        try {
            history.value = await heartbeatAPI.getHistory(limit, sessionId)
        } catch (err: any) {
            console.error('Failed to load heartbeat history:', err)
        }
    }

    async function createTask(data: CreateHeartbeatTaskRequest) {
        loading.value = true
        error.value = null
        try {
            const newTask = await heartbeatAPI.createTask(data)
            tasks.value.unshift(newTask)
            return newTask
        } catch (err: any) {
            error.value = err.message || 'Failed to create task'
            throw err
        } finally {
            loading.value = false
        }
    }

    async function updateTask(taskId: string, data: UpdateHeartbeatTaskRequest) {
        loading.value = true
        error.value = null
        try {
            const updated = await heartbeatAPI.updateTask(taskId, data)
            const index = tasks.value.findIndex(t => t.id === taskId)
            if (index !== -1) {
                tasks.value[index] = updated
            }
            return updated
        } catch (err: any) {
            error.value = err.message || 'Failed to update task'
            throw err
        } finally {
            loading.value = false
        }
    }

    async function deleteTask(taskId: string) {
        loading.value = true
        error.value = null
        try {
            await heartbeatAPI.deleteTask(taskId)
            tasks.value = tasks.value.filter(t => t.id !== taskId)
        } catch (err: any) {
            error.value = err.message || 'Failed to delete task'
            throw err
        } finally {
            loading.value = false
        }
    }

    async function runTask(taskId: string) {
        try {
            const result = await heartbeatAPI.runTask(taskId)
            await loadHistory()
            await loadTasks()
            return result
        } catch (err: any) {
            error.value = err.message || 'Failed to run task'
            throw err
        }
    }

    async function updateConfig(data: Partial<HeartbeatConfig>) {
        try {
            config.value = await heartbeatAPI.updateConfig(data)
        } catch (err: any) {
            error.value = err.message || 'Failed to update config'
            throw err
        }
    }

    async function createDefaultTasks(sessionId: string) {
        loading.value = true
        error.value = null
        try {
            const result = await heartbeatAPI.createDefaultTasks(sessionId)
            await loadTasks(sessionId)
            return result
        } catch (err: any) {
            error.value = err.message || 'Failed to create default tasks'
            throw err
        } finally {
            loading.value = false
        }
    }

    function handleHeartbeatEvent(event: HeartbeatEvent) {
        // 添加到最近事件列表（最多保留 20 条）
        recentEvents.value.unshift(event)
        if (recentEvents.value.length > 20) {
            recentEvents.value.pop()
        }

        // 更新对应任务的状态
        const taskIndex = tasks.value.findIndex(t => t.id === event.task_id)
        if (taskIndex !== -1) {
            const task = tasks.value[taskIndex]
            if (event.status === 'ok' || event.status === 'ok-empty') {
                task.status = 'idle'
                task.last_result = {
                    status: event.status,
                    preview: event.preview,
                    duration_ms: event.duration_ms,
                    output: event.preview || null,
                }
                task.last_run_at = new Date(event.ts * 1000).toISOString()
            } else if (event.status === 'failed') {
                task.status = 'error'
                task.last_error = event.reason || 'Unknown error'
            }
        }
    }

    async function initialize(sessionId?: string) {
        await Promise.all([
            loadTasks(sessionId),
            loadConfig(),
            loadMetrics(sessionId),
            loadHistory(20, sessionId),
        ])
    }

    return {
        // State
        tasks,
        config,
        metrics,
        history,
        recentEvents,
        loading,
        error,

        // Computed
        enabledTasks,
        runningTasks,
        errorTasks,
        contextUsagePercent,
        lastHeartbeat,

        // Actions
        loadTasks,
        loadConfig,
        loadMetrics,
        loadHistory,
        createTask,
        updateTask,
        deleteTask,
        runTask,
        updateConfig,
        createDefaultTasks,
        handleHeartbeatEvent,
        initialize,
    }
})
