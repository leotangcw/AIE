<template>
  <div class="heartbeat-panel">
    <!-- Header -->
    <div class="panel-header">
      <div class="header-left">
        <component :is="HeartIcon" class="header-icon" />
        <h3 class="header-title">{{ $t('heartbeat.title') || '心跳监控' }}</h3>
      </div>
      <button class="icon-btn" @click="$emit('close')" :title="$t('common.close') || '关闭'">
        <component :is="XIcon" />
      </button>
    </div>

    <!-- Metrics Overview -->
    <div class="metrics-section" v-if="metrics">
      <div class="metric-item">
        <span class="metric-label">{{ $t('heartbeat.contextLength') || 'Context' }}</span>
        <div class="metric-value-row">
          <div class="progress-bar">
            <div
              class="progress-fill"
              :class="{ warning: contextUsagePercent > 80, danger: contextUsagePercent > 95 }"
              :style="{ width: `${contextUsagePercent}%` }"
            ></div>
          </div>
          <span class="metric-value">
            {{ formatNumber(metrics.context_length) }} / {{ formatNumber(metrics.context_limit) }}
          </span>
        </div>
      </div>

      <div class="metric-item">
        <span class="metric-label">{{ $t('heartbeat.memory') || 'Memory' }}</span>
        <span class="metric-value">{{ formatBytes(metrics.memory_size) }}</span>
      </div>

      <div class="metric-item">
        <span class="metric-label">{{ $t('heartbeat.sessionIdle') || '会话空闲' }}</span>
        <span class="metric-value">
          {{ metrics.session_idle_seconds !== null ? formatDuration(metrics.session_idle_seconds) : '-' }}
        </span>
      </div>

      <div class="metric-item">
        <span class="metric-label">{{ $t('heartbeat.lastHeartbeat') || '上次心跳' }}</span>
        <span class="metric-value" :class="{ 'text-success': lastHeartbeat }">
          {{ lastHeartbeatTime }}
        </span>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'tasks' }"
        @click="activeTab = 'tasks'"
      >
        {{ $t('heartbeat.tasks') || '任务列表' }}
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'history' }"
        @click="activeTab = 'history'"
      >
        {{ $t('heartbeat.history') || '执行历史' }}
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'settings' }"
        @click="activeTab = 'settings'"
      >
        {{ $t('heartbeat.settings') || '设置' }}
      </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      <!-- Tasks Tab -->
      <div v-if="activeTab === 'tasks'" class="tasks-tab">
        <div class="task-list" v-if="tasks.length > 0">
          <div
            v-for="task in tasks"
            :key="task.id"
            class="task-item"
            :class="{ running: task.status === 'running', error: task.status === 'error' }"
          >
            <div class="task-info">
              <div class="task-name">
                <span class="status-dot" :class="task.status"></span>
                {{ task.name }}
              </div>
              <div class="task-meta">
                <span class="task-type">{{ task.task_type }}</span>
                <span class="task-schedule">
                  {{ task.schedule_type === 'interval' ? formatInterval(task.interval_seconds) : task.cron_expr }}
                </span>
              </div>
            </div>
            <div class="task-actions">
              <button class="action-btn" @click="handleRunTask(task.id)" :disabled="task.status === 'running'" :title="$t('heartbeat.runNow') || '立即执行'">
                <component :is="PlayIcon" />
              </button>
              <button class="action-btn" @click="handleDeleteTask(task.id)" :title="$t('common.delete') || '删除'">
                <component :is="TrashIcon" />
              </button>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <p>{{ $t('heartbeat.noTasks') || '暂无心跳任务' }}</p>
          <button class="btn-primary" @click="handleCreateDefault">
            {{ $t('heartbeat.createDefault') || '创建默认任务' }}
          </button>
        </div>

        <div class="add-task-section">
          <button class="btn-secondary" @click="showAddTask = true">
            <component :is="PlusIcon" />
            {{ $t('heartbeat.addTask') || '添加任务' }}
          </button>
        </div>

        <!-- Add Task Modal -->
        <div v-if="showAddTask" class="modal-overlay" @click.self="showAddTask = false">
          <div class="modal">
            <div class="modal-header">
              <h4>{{ $t('heartbeat.addTask') || '添加任务' }}</h4>
              <button class="icon-btn" @click="showAddTask = false">
                <component :is="XIcon" />
              </button>
            </div>
            <div class="modal-body">
              <div class="form-group">
                <label>{{ $t('heartbeat.taskName') || '任务名称' }}</label>
                <input v-model="newTask.name" type="text" :placeholder="$t('heartbeat.taskNamePlaceholder') || '任务名称'" />
              </div>
              <div class="form-group">
                <label>{{ $t('heartbeat.taskType') || '任务类型' }}</label>
                <select v-model="newTask.task_type">
                  <option value="HEALTH_CHECK">HEALTH_CHECK</option>
                  <option value="METRIC_COLLECT">METRIC_COLLECT</option>
                  <option value="SESSION_KEEPALIVE">SESSION_KEEPALIVE</option>
                  <option value="CUSTOM">CUSTOM</option>
                </select>
              </div>
              <div class="form-group">
                <label>{{ $t('heartbeat.scheduleType') || '调度类型' }}</label>
                <select v-model="newTask.schedule_type">
                  <option value="interval">{{ $t('heartbeat.interval') || '间隔' }}</option>
                  <option value="cron">Cron</option>
                </select>
              </div>
              <div class="form-group" v-if="newTask.schedule_type === 'interval'">
                <label>{{ $t('heartbeat.intervalSeconds') || '间隔（秒）' }}</label>
                <input v-model.number="newTask.interval_seconds" type="number" min="60" step="60" />
              </div>
              <div class="form-group" v-if="newTask.schedule_type === 'cron'">
                <label>{{ $t('heartbeat.cronExpr') || 'Cron 表达式' }}</label>
                <input v-model="newTask.cron_expr" type="text" placeholder="0 * * * *" />
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn-secondary" @click="showAddTask = false">
                {{ $t('common.cancel') || '取消' }}
              </button>
              <button class="btn-primary" @click="handleCreateTask">
                {{ $t('common.create') || '创建' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- History Tab -->
      <div v-if="activeTab === 'history'" class="history-tab">
        <div class="history-list" v-if="history.length > 0">
          <div
            v-for="(item, index) in history"
            :key="index"
            class="history-item"
            :class="{ error: item.status === 'failed' }"
          >
            <div class="history-status">
              <span class="status-indicator" :class="getStatusClass(item.status)"></span>
            </div>
            <div class="history-info">
              <div class="history-task-name">{{ item.task_name }}</div>
              <div class="history-meta">
                <span v-if="item.duration_ms">{{ item.duration_ms }}ms</span>
                <span v-if="item.last_run_at">{{ formatTimeAgo(item.last_run_at) }}</span>
              </div>
            </div>
            <div class="history-preview" v-if="item.preview">
              {{ truncate(item.preview, 50) }}
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <p>{{ $t('heartbeat.noHistory') || '暂无执行历史' }}</p>
        </div>
      </div>

      <!-- Settings Tab -->
      <div v-if="activeTab === 'settings'" class="settings-tab">
        <div class="settings-list">
          <div class="settings-item">
            <label>{{ $t('heartbeat.enabled') || '启用心跳' }}</label>
            <input
              type="checkbox"
              v-model="localConfig.enabled"
              @change="handleUpdateConfig"
            />
          </div>
          <div class="settings-item">
            <label>{{ $t('heartbeat.defaultInterval') || '默认间隔（秒）' }}</label>
            <input
              type="number"
              v-model.number="localConfig.interval_seconds"
              min="60"
              step="60"
              @change="handleUpdateConfig"
            />
          </div>
          <div class="settings-item">
            <label>{{ $t('heartbeat.activeHours') || '生效时段' }}</label>
            <div class="active-hours-inputs">
              <input
                v-model="localConfig.active_hours.start"
                type="time"
                @change="handleUpdateConfig"
              />
              <span>-</span>
              <input
                v-model="localConfig.active_hours.end"
                type="time"
                @change="handleUpdateConfig"
              />
            </div>
          </div>
        </div>

        <div class="settings-actions">
          <button class="btn-secondary" @click="handleRefreshAll">
            <component :is="RefreshIcon" />
            {{ $t('heartbeat.refreshAll') || '刷新全部' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useHeartbeatStore } from '@/store/heartbeat'
import {
  Heart as HeartIcon,
  X as XIcon,
  Play as PlayIcon,
  Trash as TrashIcon,
  Plus as PlusIcon,
  RefreshCw as RefreshIcon,
} from 'lucide-vue-next'

// Props
interface Props {
  sessionId?: string
}

const props = defineProps<Props>()

// Emits
defineEmits(['close'])

// Store
const store = useHeartbeatStore()

// State
const activeTab = ref<'tasks' | 'history' | 'settings'>('tasks')
const showAddTask = ref(false)

const newTask = reactive({
  name: '',
  task_type: 'HEALTH_CHECK',
  schedule_type: 'interval',
  interval_seconds: 1800,
  cron_expr: '',
})

const localConfig = reactive({
  enabled: true,
  interval_seconds: 1800,
  active_hours: {
    start: '08:00',
    end: '22:00',
    timezone: 'Asia/Shanghai',
  },
})

// Computed
const metrics = computed(() => store.metrics)
const tasks = computed(() => store.tasks)
const history = computed(() => store.history)
const contextUsagePercent = computed(() => store.contextUsagePercent)
const lastHeartbeat = computed(() => store.lastHeartbeat)

const lastHeartbeatTime = computed(() => {
  if (!lastHeartbeat.value?.last_run_at) return '-'
  return formatTimeAgo(lastHeartbeat.value.last_run_at)
})

// Methods
function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

function formatBytes(bytes: number): string {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

function formatInterval(seconds: number | null): string {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000)

  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function getStatusClass(status: string | null): string {
  if (!status) return ''
  if (status === 'ok' || status === 'ok-empty') return 'success'
  if (status === 'failed') return 'error'
  return ''
}

function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.substring(0, length) + '...'
}

async function handleRunTask(taskId: string) {
  try {
    await store.runTask(taskId)
  } catch (err) {
    console.error('Failed to run task:', err)
  }
}

async function handleDeleteTask(taskId: string) {
  if (!confirm('确定要删除这个任务吗？')) return
  try {
    await store.deleteTask(taskId)
  } catch (err) {
    console.error('Failed to delete task:', err)
  }
}

async function handleCreateTask() {
  if (!newTask.name.trim()) {
    alert('请输入任务名称')
    return
  }

  try {
    await store.createTask({
      session_id: props.sessionId || 'default',
      name: newTask.name,
      task_type: newTask.task_type,
      schedule_type: newTask.schedule_type,
      interval_seconds: newTask.schedule_type === 'interval' ? newTask.interval_seconds : undefined,
      cron_expr: newTask.schedule_type === 'cron' ? newTask.cron_expr : undefined,
    })
    showAddTask.value = false
    // Reset form
    newTask.name = ''
    newTask.task_type = 'HEALTH_CHECK'
    newTask.schedule_type = 'interval'
    newTask.interval_seconds = 1800
    newTask.cron_expr = ''
  } catch (err) {
    console.error('Failed to create task:', err)
  }
}

async function handleCreateDefault() {
  try {
    await store.createDefaultTasks(props.sessionId || 'default')
  } catch (err) {
    console.error('Failed to create default tasks:', err)
  }
}

async function handleUpdateConfig() {
  try {
    await store.updateConfig({
      enabled: localConfig.enabled,
      interval_seconds: localConfig.interval_seconds,
    })
  } catch (err) {
    console.error('Failed to update config:', err)
  }
}

async function handleRefreshAll() {
  await Promise.all([
    store.loadTasks(props.sessionId),
    store.loadMetrics(props.sessionId),
    store.loadHistory(20, props.sessionId),
  ])
}

// Lifecycle
onMounted(async () => {
  await store.initialize(props.sessionId)
  // Sync local config with store
  if (store.config) {
    localConfig.enabled = store.config.enabled
    localConfig.interval_seconds = store.config.interval_seconds
    if (store.config.active_hours) {
      localConfig.active_hours = { ...store.config.active_hours }
    }
  }
})
</script>

<style scoped>
.heartbeat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.header-icon {
  width: 20px;
  height: 20px;
  color: var(--color-danger);
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.metrics-section {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.metric-label {
  color: var(--text-secondary);
}

.metric-value {
  color: var(--text-primary);
  font-family: monospace;
}

.metric-value-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.progress-bar {
  width: 60px;
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-success);
  transition: width 0.3s ease;
}

.progress-fill.warning {
  background: var(--color-warning);
}

.progress-fill.danger {
  background: var(--color-danger);
}

.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
}

.tab {
  flex: 1;
  padding: var(--spacing-sm) var(--spacing-md);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-secondary);
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  transition: all 0.2s;
}

.task-item:hover {
  background: var(--bg-hover);
}

.task-item.running {
  border-left: 3px solid var(--color-warning);
}

.task-item.error {
  border-left: 3px solid var(--color-danger);
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.task-name {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 13px;
  font-weight: 500;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
}

.status-dot.running {
  background: var(--color-warning);
  animation: pulse 1s infinite;
}

.status-dot.error {
  background: var(--color-danger);
}

.status-dot.disabled {
  background: var(--text-secondary);
}

.task-meta {
  display: flex;
  gap: var(--spacing-sm);
  font-size: 11px;
  color: var(--text-secondary);
}

.task-type {
  font-family: monospace;
  background: var(--bg-primary);
  padding: 1px 4px;
  border-radius: 2px;
}

.task-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.action-btn {
  padding: 4px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.empty-state {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
}

.empty-state p {
  margin-bottom: var(--spacing-md);
}

.add-task-section {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.btn-primary,
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  border: none;
  border-radius: var(--radius-md);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  background: var(--color-primary-hover);
}

.btn-secondary {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.btn-secondary:hover {
  background: var(--bg-hover);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.history-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.history-item.error {
  border-left: 3px solid var(--color-danger);
}

.history-status {
  padding-top: 2px;
}

.status-indicator {
  display: block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
}

.status-indicator.error {
  background: var(--color-danger);
}

.history-info {
  flex: 1;
}

.history-task-name {
  font-size: 12px;
  font-weight: 500;
}

.history-meta {
  display: flex;
  gap: var(--spacing-sm);
  font-size: 11px;
  color: var(--text-secondary);
  font-family: monospace;
}

.history-preview {
  font-size: 11px;
  color: var(--text-secondary);
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.settings-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.settings-item label {
  color: var(--text-secondary);
}

.settings-item input[type='number'] {
  width: 80px;
  padding: var(--spacing-xs) var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-family: monospace;
}

.settings-item input[type='checkbox'] {
  width: 16px;
  height: 16px;
}

.active-hours-inputs {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.active-hours-inputs input {
  padding: var(--spacing-xs);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-family: monospace;
  width: 80px;
}

.settings-actions {
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 400px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h4 {
  margin: 0;
  font-size: 14px;
}

.modal-body {
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-group label {
  font-size: 12px;
  color: var(--text-secondary);
}

.form-group input,
.form-group select {
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 13px;
}

.form-group select {
  cursor: pointer;
}

.text-success {
  color: var(--color-success);
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
