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
          :disabled="taskStore.loading"
          @click="handleRefresh"
        >
          <component
            :is="RefreshIcon"
            :size="12"
            :class="{ 'spin': taskStore.loading }"
          />
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div
      v-if="taskStore.loading"
      class="loading-state"
    >
      <component
        :is="LoaderIcon"
        :size="32"
        class="spin"
      />
      <p>{{ $t('common.loading') }}</p>
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
          <span class="module-count">({{ taskStore.systemTasks.length }})</span>
        </div>
        <div
          v-if="expandedModules.system"
          class="module-body"
        >
          <div
            v-if="taskStore.systemTasks.length === 0"
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
            v-for="task in taskStore.systemTasks"
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
          <span class="module-count">({{ taskStore.runningTasks.length }})</span>
        </div>
        <div
          v-if="expandedModules.running"
          class="module-body"
        >
          <div
            v-if="taskStore.runningTasks.length === 0"
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
            v-for="task in taskStore.runningTasks"
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
          <span class="module-count">({{ taskStore.doneTasks.length }})</span>
        </div>
        <div
          v-if="expandedModules.done"
          class="module-body"
        >
          <div
            v-if="taskStore.doneTasks.length === 0"
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
            v-for="task in taskStore.doneTasks"
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
  Clock as ClockIcon,
  Zap as ZapIcon,
  Archive as ArchiveIcon,
  Inbox as InboxIcon,
  Calendar as CalendarIcon,
  ChevronDown as ChevronDownIcon,
  ChevronRight as ChevronRightIcon,
  CheckCircle as CheckCircleIcon,
} from 'lucide-vue-next'
import { useTaskStore } from '@/store/tasks'
import { useChatStore } from '@/store/chat'
import type { TaskItem } from '@/api/endpoints'

const { t } = useI18n()
const taskStore = useTaskStore()
const chatStore = useChatStore()

// 展开/折叠状态
const expandedModules = ref({
  system: false,    // 周期任务默认折叠
  running: true,    // 进行中默认展开
  done: false,      // 已完成默认折叠
})

const toggleModule = (module: 'system' | 'running' | 'done') => {
  expandedModules.value[module] = !expandedModules.value[module]
}

const handleRefresh = () => {
  taskStore.loadTasks(chatStore.currentSessionId)
}

// Helper functions
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

const getTaskTypeText = (taskType?: string): string => {
  const typeMap: Record<string, string> = {
    'subagent': '子代理',
    'cron': '定时任务',
    'manual': '手动任务',
    'workflow': '工作流',
  }
  return taskType ? (typeMap[taskType] || taskType) : ''
}

const truncateDesc = (desc?: string): string => {
  if (!desc) return ''
  return desc.length > 60 ? desc.substring(0, 60) + '...' : desc
}

const calculateRuntime = (task: TaskItem): number => {
  if (!task.started_at) return 0
  const start = new Date(task.started_at).getTime()
  const now = Date.now()
  return Math.floor((now - start) / 1000)
}

const getTaskProgress = (task: TaskItem): number => {
  if (task.status === 'done') {
    return 100
  }

  if (task.progress > 0) return task.progress

  if (task.estimated_duration && task.started_at && task.status === 'running') {
    const runtime = calculateRuntime(task)
    const progress = Math.floor((runtime / task.estimated_duration) * 100)
    if (progress > 100) {
      return -1
    }
    return Math.min(progress, 95)
  }

  return 0
}

const isOvertime = (task: TaskItem): boolean => {
  if (!task.estimated_duration || !task.started_at) return false
  const runtime = calculateRuntime(task)
  return runtime > task.estimated_duration * 1.5
}

// Lifecycle: 初始加载 + 低频兜底轮询
let fallbackInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  taskStore.loadTasks(chatStore.currentSessionId)
  // 低频兜底轮询 (60s) - 纯 HTTP GET DB 状态，不调 LLM
  fallbackInterval = setInterval(() => {
    taskStore.refreshFromServer(chatStore.currentSessionId)
  }, 60000)
})

onUnmounted(() => {
  if (fallbackInterval) {
    clearInterval(fallbackInterval)
  }
})

// Watch session changes
watch(() => chatStore.currentSessionId, () => {
  taskStore.loadTasks(chatStore.currentSessionId)
})
</script>

<style scoped>
.task-board {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: auto;
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
