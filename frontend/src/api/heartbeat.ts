/**
 * Heartbeat API Client
 */

import apiClient from './client'

// ============================================================================
// Types
// ============================================================================

export interface ActiveHours {
    start: string
    end: string
    timezone: string
}

export interface HeartbeatTask {
    id: string
    session_id: string
    name: string
    task_type: 'HEALTH_CHECK' | 'METRIC_COLLECT' | 'SESSION_KEEPALIVE' | 'CUSTOM'
    schedule_type: 'interval' | 'cron'
    interval_seconds: number | null
    cron_expr: string | null
    active_hours: ActiveHours | null
    config: Record<string, any> | null
    prompt_template: string | null
    status: 'idle' | 'running' | 'error' | 'disabled'
    last_run_at: string | null
    last_result: {
        status: string
        preview: string | null
        duration_ms: number | null
        output: string | null
    } | null
    last_error: string | null
    next_run_at: string | null
    enabled: boolean
    created_at: string
    updated_at: string
}

export interface CreateHeartbeatTaskRequest {
    session_id: string
    name: string
    task_type: string
    schedule_type?: string
    interval_seconds?: number
    cron_expr?: string
    active_hours?: ActiveHours | null
    config?: Record<string, any> | null
    prompt_template?: string | null
    enabled?: boolean
}

export interface UpdateHeartbeatTaskRequest {
    name?: string
    schedule_type?: string
    interval_seconds?: number
    cron_expr?: string
    active_hours?: ActiveHours | null
    config?: Record<string, any> | null
    prompt_template?: string | null
    enabled?: boolean
}

export interface HeartbeatConfig {
    enabled: boolean
    interval_seconds: number
    active_hours: ActiveHours | null
}

export interface HeartbeatMetrics {
    context_length: number
    context_limit: number
    memory_size: number
    queue_depth: number
    session_idle_seconds: number | null
    timestamp: string
}

export interface HeartbeatEvent {
    task_id: string
    task_name: string
    status: 'sent' | 'ok-empty' | 'ok' | 'skipped' | 'failed'
    preview: string | null
    duration_ms: number | null
    ts: number
    reason: string | null
    indicator_type: 'ok' | 'alert' | 'error' | null
}

export interface HeartbeatHistoryItem {
    task_id: string
    task_name: string
    task_type: string
    status: string | null
    preview: string | null
    duration_ms: number | null
    last_run_at: string | null
    last_error: string | null
}

// ============================================================================
// API Endpoints
// ============================================================================

export const heartbeatAPI = {
    // 获取任务列表
    getTasks: (sessionId?: string): Promise<HeartbeatTask[]> =>
        apiClient.get('/heartbeat/tasks', { params: sessionId ? { session_id: sessionId } : {} }),

    // 创建任务
    createTask: (data: CreateHeartbeatTaskRequest): Promise<HeartbeatTask> =>
        apiClient.post('/heartbeat/tasks', data),

    // 更新任务
    updateTask: (taskId: string, data: UpdateHeartbeatTaskRequest): Promise<HeartbeatTask> =>
        apiClient.patch(`/heartbeat/tasks/${taskId}`, data),

    // 删除任务
    deleteTask: (taskId: string): Promise<{ success: boolean; message: string }> =>
        apiClient.delete(`/heartbeat/tasks/${taskId}`),

    // 立即执行任务
    runTask: (taskId: string): Promise<{
        success: boolean
        task_id: string
        status: string
        preview: string | null
        error: string | null
    }> =>
        apiClient.post(`/heartbeat/tasks/${taskId}/run`),

    // 获取全局配置
    getConfig: (): Promise<HeartbeatConfig> =>
        apiClient.get('/heartbeat/config'),

    // 更新全局配置
    updateConfig: (data: Partial<HeartbeatConfig>): Promise<HeartbeatConfig> =>
        apiClient.put('/heartbeat/config', data),

    // 获取执行历史
    getHistory: (limit?: number, sessionId?: string): Promise<HeartbeatHistoryItem[]> =>
        apiClient.get('/heartbeat/history', {
            params: {
                ...(limit && { limit }),
                ...(sessionId && { session_id: sessionId }),
            },
        }),

    // 获取当前指标
    getMetrics: (sessionId?: string): Promise<HeartbeatMetrics> =>
        apiClient.get('/heartbeat/metrics', { params: sessionId ? { session_id: sessionId } : {} }),

    // 创建默认任务
    createDefaultTasks: (sessionId: string): Promise<{
        success: boolean
        created: number
        tasks: HeartbeatTask[]
    }> =>
        apiClient.post('/heartbeat/tasks/default', null, { params: { session_id: sessionId } }),
}
