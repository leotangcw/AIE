<template>
  <div class="task-board">
    <!-- Header -->
    <div class="task-header">
      <div class="header-content">
        <h2 class="title">
          {{ $t('taskBoard.title') }}
        </h2>
        <p class="description">
          {{ $t('taskBoard.description') }}
        </p>
      </div>
      <div class="header-actions">
        <button
          class="refresh-btn"
          :disabled="loading"
          @click="handleRefresh"
        >
          <component
            :is="RefreshIcon"
            :size="12"
            :class="{ 'spin': loading }"
          />
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div
      v-if="loading"
      class="loading-state"
    >
      <component
        :is="LoaderIcon"
        :size="32"
        class="spin"
      />
      <p>{{ $t('common.loading') }}</p>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="error-state"
    >
      <component
        :is="AlertCircleIcon"
        :size="32"
      />
      <p>{{ error }}</p>
      <button
        class="retry-btn"
        @click="loadTasks"
      >
        {{ $t('common.retry') }}
      </button>
    </div>

    <!-- Task Board Content -->
    <div
      v-else
      class="task-content"
    >
      <!-- 周期任务模块 (SYSTEM) -->
      <div class="task-module">
        <div
          class="module-header"
          @click="toggleModule('system')"
        >
          <component
            :is="expandedModules.system ? ChevronDownIcon : ChevronRightIcon"
            :size="16"
          />
          <component
            :is="ClockIcon"
            :size="16"
          />
          <span class="module-title">{{ $t('taskBoard.systemTasks') }}</span>
          <span class="module-count">({{ systemTasks.length }})</span>
        </div>
        <div
          v-if="expandedModules.system"
          class="module-body"
        >
          <div
            v-if="systemTasks.length === 0"
            class="empty-state"
          >
            <component
              :is="CalendarIcon"
              :size="24"
            />
            <p>{{ $t('taskBoard.noSystemTasks') }}</p>
          </div>
          <div
            v-else
            v-for="task in systemTasks"
            :key="task.id"
            class="task-item"
            :class="`status-${task.status}`"
          >
            <span class="task-icon">{{ getStatusIcon(task.status) }}</span>
            <div class="task-info">
              <span class="task-title">{{ task.title }}</span>
              <span class="task-schedule">{{ task.cron_expression }}</span>
            </div>
            <span
              class="task-status"
              :class="task.status"
            >
              {{ getStatusText(task.last_run_status || task.status) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 进行中的任务模块 (SESSION) -->
      <div class="task-module">
        <div
          class="module-header"
          @click="toggleModule('running')"
        >
          <component
            :is="expandedModules.running ? ChevronDownIcon : ChevronRightIcon"
            :size="16"
          />
          <component
            :is="ZapIcon"
            :size="16"
          />
          <span class="module-title">{{ $t('taskBoard.runningTasks') }}</span>
          <span class="module-count">({{ runningTasks.length }})</span>
        </div>
        <div
          v-if="expandedModules.running"
          class="module-body"
        >
          <div
            v-if="runningTasks.length === 0"
            class="empty-state"
          >
            <component
              :is="CheckCircleIcon"
              :size="24"
            />
            <p>{{ $t('taskBoard.noRunningTasks') }}</p>
          </div>
          <div
            v-else
            v-for="task in runningTasks"
            :key="task.id"
            class="task-item"
            :class="`status-${task.status}`"
          >
            <span class="task-icon">{{ getStatusIcon(task.status) }}</span>
            <div class="task-info">
              <span class="task-title">{{ task.title }}</span>
              <!-- 显示任务类型和描述 -->
              <div class="task-meta">
                <span class="task-type">{{ getTaskTypeText(task.task_type) }}</span>
                <span v-if="task.description" class="task-desc" :title="task.description">
                  {{ truncateDesc(task.description) }}
                </span>
              </div>
              <!-- 已完成：显示实际耗时 -->
              <div v-if="task.status === 'done' && task.actual_duration" class="task-runtime">
                完成，耗时 {{ formatDuration(task.actual_duration) }}
              </div>
              <!-- 运行中：显示进度或运行时间 -->
              <div v-else-if="task.status === 'running'">
                <div
                  v-if="getTaskProgress(task) > 0"
                  class="task-progress"
                >
                  <div
                    class="progress-bar"
                    :class="{ 'over-time': getTaskProgress(task) === -1 || isOvertime(task) }"
                    :style="{ width: `${getTaskProgress(task) === -1 ? 100 : Math.min(getTaskProgress(task), 100)}%` }"
                  />
                  <span class="progress-text">
                    {{ getTaskProgress(task) === -1 ? '已超时' : getTaskProgress(task) + '%' }}
                    <span v-if="getTaskProgress(task) === -1 || isOvertime(task)" class="overtime-warning">已运行 {{ formatDuration(calculateRuntime(task)) }}</span>
                  </span>
                </div>
                <div v-else-if="task.started_at" class="task-runtime">
                  已运行 {{ formatDuration(calculateRuntime(task)) }}
                  <span v-if="task.estimated_duration"> / 预估 {{ formatDuration(task.estimated_duration) }}</span>
                </div>
              </div>
              <!-- 其他状态 -->
              <div v-else-if="task.started_at" class="task-runtime">
                已运行 {{ formatDuration(calculateRuntime(task)) }}
              </div>
            </div>
            <span
              class="task-status"
              :class="task.status"
            >
              {{ getStatusText(task.status) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 已完成任务模块 (SESSION) -->
      <div class="task-module">
        <div
          class="module-header"
          @click="toggleModule('done')"
        >
          <component
            :is="expandedModules.done ? ChevronDownIcon : ChevronRightIcon"
            :size="16"
          />
          <component
            :is="ArchiveIcon"
            :size="16"
          />
          <span class="module-title">{{ $t('taskBoard.doneTasks') }}</span>
          <span class="module-count">({{ doneTasks.length }})</span>
        </div>
        <div
          v-if="expandedModules.done"
          class="module-body"
        >
          <div
            v-if="doneTasks.length === 0"
            class="empty-state"
          >
            <component
              :is="InboxIcon"
              :size="24"
            />
            <p>{{ $t('taskBoard.noDoneTasks') }}</p>
          </div>
          <div
            v-else
            v-for="task in doneTasks"
            :key="task.id"
            class="task-item status-done"
          >
            <span class="task-icon">{{ getStatusIcon('done') }}</span>
            <div class="task-info">
              <span class="task-title">{{ task.title }}</span>
              <span class="task-time">
                {{ formatTime(task.completed_at) }}
                <span v-if="task.actual_duration">
                  · {{ formatDuration(task.actual_duration) }}
                </span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  RefreshCw as RefreshIcon,
  Loader2 as LoaderIcon,
  AlertCircle as AlertCircleIcon,
  Clock as ClockIcon,
  Zap as ZapIcon,
  Archive as ArchiveIcon,
  Inbox as InboxIcon,
  Calendar as CalendarIcon,
  ChevronDown as ChevronDownIcon,
  ChevronRight as ChevronRightIcon,
  CheckCircle as CheckCircleIcon,
} from 'lucide-vue-next'
import { taskBoardAPI, type TaskItem } from '@/api/endpoints'
import { useChatStore } from '@/store/chat'

const { t } = useI18n()
const chatStore = useChatStore()

// State
const loading = ref(false)
const error = ref<string | null>(null)
const systemTasks = ref<TaskItem[]>([])
const runningTasks = ref<TaskItem[]>([])
const doneTasks = ref<TaskItem[]>([])

// 展开/折叠状态
const expandedModules = ref({
  system: false,    // 周期任务默认折叠
  running: true,    // 进行中默认展开
  done: false,      // 已完成默认折叠
})

// Methods
const toggleModule = (module: 'system' | 'running' | 'done') => {
  expandedModules.value[module] = !expandedModules.value[module]
}

// 刷新状态 - 不会导致整个loading
const isRefreshing = ref(false)
const refreshingTaskIds = ref<Set<string>>(new Set())

const loadTasks = async () => {
  // 防止重复加载基本数据
  if (loading.value) return

  loading.value = true
  error.value = null

  try {
    // 获取周期任务 - 后端直接返回数组
    const systemRes = await taskBoardAPI.getSystemTasks()
    systemTasks.value = Array.isArray(systemRes) ? systemRes : (systemRes.tasks || [])

    // 获取当前会话的任务
    const sessionId = chatStore.currentSessionId
    if (sessionId) {
      const sessionRes = await taskBoardAPI.getSessionTasks(sessionId)
      runningTasks.value = sessionRes.running_tasks || []
      doneTasks.value = sessionRes.done_tasks || []
    } else {
      runningTasks.value = []
      doneTasks.value = []
    }
  } catch (e: any) {
    console.error('Failed to load tasks:', e)
    systemTasks.value = []
    runningTasks.value = []
    doneTasks.value = []
    error.value = null
  } finally {
    loading.value = false
  }
}

// 后台刷新任务进度 - 不阻塞UI
const refreshTaskProgress = async () => {
  if (isRefreshing.value || runningTasks.value.length === 0) return

  isRefreshing.value = true

  try {
    // 并行刷新所有运行中的任务
    const refreshPromises = runningTasks.value
      .filter(task => !refreshingTaskIds.value.has(task.id))
      .map(async (task) => {
        refreshingTaskIds.value.add(task.id)
        try {
          const refreshResult = await taskBoardAPI.refreshTask(task.id)

          // 更新任务信息
          if (refreshResult.progress !== undefined) {
            task.progress = refreshResult.progress
          }
          if (refreshResult.status === 'done' || refreshResult.status === 'failed') {
            // 如果任务完成了，移到已完成列表
            const index = runningTasks.value.findIndex(t => t.id === task.id)
            if (index !== -1) {
              runningTasks.value.splice(index, 1)
              task.status = refreshResult.status
              doneTasks.value.unshift(task)
            }
          }
          // 更新描述（包含进度信息）
          if (refreshResult.description) {
            task.description = refreshResult.description
          }
        } catch (refreshError) {
          console.warn(`Failed to refresh task ${task.id}:`, refreshError)
        } finally {
          refreshingTaskIds.value.delete(task.id)
        }
      })

    await Promise.all(refreshPromises)
  } finally {
    isRefreshing.value = false
  }
}

const handleRefresh = () => {
  loadTasks()
}

const getStatusIcon = (status: string): string => {
  const iconMap: Record<string, string> = {
    pending: '○',
    running: '🔄',
    done: '✓',
    failed: '✗',
    cancelled: '⊘',
  }
  return iconMap[status] || '○'
}

const getStatusText = (status: string): string => {
  const textMap: Record<string, string> = {
    pending: t('taskBoard.status.pending'),
    running: t('taskBoard.status.running'),
    done: t('taskBoard.status.done'),
    failed: t('taskBoard.status.failed'),
    cancelled: t('taskBoard.status.cancelled'),
    ok: t('taskBoard.status.ok'),
    error: t('taskBoard.status.error'),
  }
  return textMap[status] || status
}

const formatTime = (timeStr?: string): string => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const formatDuration = (seconds: number): string => {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}min`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}min`
}

// 获取任务类型的中文描述
const getTaskTypeText = (taskType?: string): string => {
  const typeMap: Record<string, string> = {
    'subagent': '子代理',
    'cron': '定时任务',
    'manual': '手动任务',
    'workflow': '工作流',
  }
  return taskType ? (typeMap[taskType] || taskType) : ''
}

// 截断任务描述
const truncateDesc = (desc?: string): string => {
  if (!desc) return ''
  return desc.length > 60 ? desc.substring(0, 60) + '...' : desc
}

// 计算任务已运行时间（秒）
const calculateRuntime = (task: TaskItem): number => {
  if (!task.started_at) return 0
  const start = new Date(task.started_at).getTime()
  const now = Date.now()
  return Math.floor((now - start) / 1000)
}

// 计算任务进度百分比
const getTaskProgress = (task: TaskItem): number => {
  // 已完成的任务不显示进度条（或显示100%）
  if (task.status === 'done') {
    return 100
  }

  // 优先使用后端返回的进度
  if (task.progress > 0) return task.progress

  // 如果没有进度但有预估时长，根据已运行时间计算
  // 注意：只有运行中的任务才计算进度
  if (task.estimated_duration && task.started_at && task.status === 'running') {
    const runtime = calculateRuntime(task)
    const progress = Math.floor((runtime / task.estimated_duration) * 100)
    // 如果超过预估时长，进度不再增加，显示实际运行时长
    if (progress > 100) {
      return -1 // 表示已超时
    }
    return Math.min(progress, 95)
  }

  return 0
}

// 检查是否超时
const isOvertime = (task: TaskItem): boolean => {
  if (!task.estimated_duration || !task.started_at) return false
  const runtime = calculateRuntime(task)
  // 超过预估时长的 1.5 倍视为超时
  return runtime > task.estimated_duration * 1.5
}

// Lifecycle
onMounted(() => {
  loadTasks()
  // 自适应刷新：初始每3秒刷新一次
  startAutoRefresh(3000)
})

// 自适应刷新逻辑
let autoRefreshInterval: ReturnType<typeof setInterval> | null = null
let currentRefreshInterval = 60000 // 初始刷新间隔（毫秒）
const FAST_INTERVAL = 30000   // 有任务时快速刷新：30秒
const SLOW_INTERVAL = 120000  // 无任务时慢速刷新：2分钟

const startAutoRefresh = (interval: number) => {
  // 清除旧的定时器
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval)
  }

  // 设置新的定时器 - 后台刷新进度，不阻塞UI
  autoRefreshInterval = setInterval(async () => {
    // 先保存当前任务状态
    const hadRunningTasks = runningTasks.value.length > 0

    // 后台刷新任务进度
    await refreshTaskProgress()

    // 同时定期重新加载基本数据（较慢的刷新）
    if (Math.random() < 0.3) { // 30%概率同时刷新基本数据
      await loadTasks()
    }

    // 根据是否有运行中任务调整刷新频率
    const hasRunningNow = runningTasks.value.length > 0

    // 如果从无任务变成有任务，或者从有任务变成无任务，调整频率
    if (hasRunningNow && !hadRunningTasks) {
      // 开始新任务，加快刷新
      currentRefreshInterval = FAST_INTERVAL
      startAutoRefresh(FAST_INTERVAL)
    } else if (!hasRunningNow && hadRunningTasks) {
      // 任务都完成了，减慢刷新
      currentRefreshInterval = SLOW_INTERVAL
      startAutoRefresh(SLOW_INTERVAL)
    }
  }, interval)
}

onUnmounted(() => {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval)
  }
})

// Watch session changes
watch(() => chatStore.currentSessionId, () => {
  loadTasks()
})
</script>

<style scoped>
.task-board {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
}

.header-content {
  flex: 1;
}

.title {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.description {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 2px;
}

.refresh-btn,
.create-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  padding: 0;
  border: none;
  border-radius: 2px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover,
.create-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: var(--text-secondary);
}

.loading-state .spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.retry-btn {
  margin-top: 12px;
  padding: 6px 16px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.task-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.task-module {
  margin-bottom: 8px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.module-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  cursor: pointer;
  user-select: none;
}

.module-header:hover {
  background: var(--bg-hover);
}

.module-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.module-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.module-body {
  background: var(--bg-primary);
}

.task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-left: 3px solid transparent;
}

.task-item.status-pending {
  border-left-color: #9CA3AF;
}

.task-item.status-running {
  border-left-color: #3B82F6;
}

.task-item.status-done {
  border-left-color: #22C55E;
}

.task-item.status-failed {
  border-left-color: #EF4444;
}

.task-item.status-cancelled {
  border-left-color: #9CA3AF;
}

.task-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.task-info {
  flex: 1;
  min-width: 0;
}

.task-title {
  display: block;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-schedule {
  font-size: 11px;
  color: var(--text-secondary);
}

.task-time {
  font-size: 11px;
  color: var(--text-secondary);
}

.task-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.progress-bar {
  height: 4px;
  background: #3B82F6;
  border-radius: 2px;
  max-width: 100px;
  transition: width 0.3s ease;
}

.progress-bar.over-time {
  background: #F59E0B; /* 警告橙色 */
}

.progress-text {
  font-size: 11px;
  color: var(--text-secondary);
}

.overtime-warning {
  color: #F59E0B;
  margin-left: 4px;
}

.task-runtime {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  font-size: 11px;
}

.task-type {
  padding: 1px 6px;
  background: var(--bg-secondary);
  border-radius: 3px;
  color: var(--text-secondary);
}

.task-desc {
  color: var(--text-secondary);
  opacity: 0.8;
}

.task-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.task-status.pending {
  background: #374151;
  color: #9CA3AF;
}

.task-status.running {
  background: #1E3A5F;
  color: #3B82F6;
}

.task-status.done {
  background: #14532D;
  color: #22C55E;
}

.task-status.failed {
  background: #450A0A;
  color: #EF4444;
}

.task-status.ok {
  background: #14532D;
  color: #22C55E;
}

.task-status.error {
  background: #450A0A;
  color: #EF4444;
}

.empty-state {
  padding: 24px;
  font-size: 13px;
}

.empty-state svg {
  margin-bottom: 8px;
  opacity: 0.5;
}
</style>
