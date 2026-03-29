<template>
  <div class="heartbeat-widget">
    <!-- 心跳状态栏 -->
    <div class="heartbeat-status">
      <div class="status-left">
        <Heart :size="14" class="heart-icon" :class="{ active: isActive }" />
        <span class="status-label">{{ $t('heartbeat.title') }}</span>
      </div>
      <div class="status-right">
        <span class="status-dot" :class="statusClass"></span>
        <span class="status-text">{{ statusText }}</span>
      </div>
    </div>

    <!-- 指标行 -->
    <div class="metrics-row">
      <div class="metric" :title="$t('heartbeat.contextLength')">
        <span class="metric-label">{{ $t('heartbeat.ctx') }}</span>
        <div class="metric-bar">
          <div class="metric-fill" :style="{ width: `${contextPercent}%` }" :class="contextClass"></div>
        </div>
        <span class="metric-value">{{ formatNum(metrics?.context_length || 0) }}</span>
      </div>

      <div class="metric" :title="$t('heartbeat.memory')">
        <span class="metric-label">{{ $t('heartbeat.mem') }}</span>
        <span class="metric-value">{{ formatBytes(metrics?.memory_size || 0) }}</span>
      </div>

      <div class="metric" :title="$t('heartbeat.sessionIdle')">
        <span class="metric-label">{{ $t('heartbeat.idle') }}</span>
        <span class="metric-value">{{ formatDuration(metrics?.session_idle_seconds) }}</span>
      </div>
    </div>

    <!-- 最近任务状态 -->
    <div class="tasks-row" v-if="tasks.length > 0">
      <div
        v-for="task in displayTasks"
        :key="task.id"
        class="task-indicator"
        :class="task.status"
        :title="`${task.name}: ${task.status}`"
      >
        <span class="task-dot"></span>
        <span class="task-name">{{ task.name }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Heart } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { heartbeatAPI, type HeartbeatTask, type HeartbeatMetrics } from '@/api/heartbeat'

const { t } = useI18n()

// State
const metrics = ref<HeartbeatMetrics | null>(null)
const tasks = ref<HeartbeatTask[]>([])
const history = ref<any[]>([])
const isActive = ref(true)
const loading = ref(false)

// Computed
const contextPercent = computed(() => {
  if (!metrics.value) return 0
  return Math.min(100, Math.round((metrics.value.context_length / metrics.value.context_limit) * 100))
})

const contextClass = computed(() => {
  if (contextPercent.value > 95) return 'danger'
  if (contextPercent.value > 80) return 'warning'
  return ''
})

const lastEvent = computed(() => history.value[0] || null)

const statusClass = computed(() => {
  if (loading.value) return 'loading'
  if (!isActive.value) return 'inactive'
  if (lastEvent.value?.status === 'failed') return 'error'
  if (lastEvent.value) return 'ok'
  return 'idle'
})

const statusText = computed(() => {
  if (loading.value) return t('common.loading')
  if (!isActive.value) return t('heartbeat.statusInactive')
  if (lastEvent.value?.status === 'failed') return t('heartbeat.statusError')
  if (lastEvent.value) return formatTimeAgo(lastEvent.value.last_run_at)
  return t('heartbeat.statusIdle')
})

const displayTasks = computed(() => {
  const filtered = tasks.value.filter(t => t.task_type !== 'HEALTH_CHECK' && t.task_type !== 'METRIC_COLLECT')
  return filtered.slice(0, 3)
})

// Methods
function formatNum(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toString()
}

function formatBytes(b: number): string {
  if (b >= 1048576) return (b / 1048576).toFixed(1) + 'M'
  if (b >= 1024) return (b / 1024).toFixed(1) + 'K'
  return b + 'B'
}

function formatDuration(s: number | null | undefined): string {
  if (s == null) return '-'
  if (s < 60) return Math.round(s) + 's'
  if (s < 3600) return Math.round(s / 60) + 'm'
  return Math.round(s / 3600) + 'h'
}

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const now = new Date()
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000)
  if (diff < 60) return diff + 's'
  if (diff < 3600) return Math.floor(diff / 60) + 'm'
  if (diff < 86400) return Math.floor(diff / 3600) + 'h'
  return Math.floor(diff / 86400) + 'd'
}

async function loadData() {
  loading.value = true
  try {
    const [metricsData, tasksData, historyData] = await Promise.all([
      heartbeatAPI.getMetrics().catch(() => null),
      heartbeatAPI.getTasks().catch(() => []),
      heartbeatAPI.getHistory(5).catch(() => []),
    ])
    // 仅在数据变化时更新，避免不必要的响应式更新
    if (JSON.stringify(metricsData) !== JSON.stringify(metrics.value)) {
      metrics.value = metricsData
    }
    if (JSON.stringify(tasksData) !== JSON.stringify(tasks.value)) {
      tasks.value = tasksData
    }
    if (JSON.stringify(historyData) !== JSON.stringify(history.value)) {
      history.value = historyData
    }
  } catch (e) {
    console.error('Failed to load heartbeat data:', e)
  } finally {
    loading.value = false
  }
}

// Refresh interval
let refreshInterval: number | null = null

onMounted(() => {
  loadData()
  refreshInterval = window.setInterval(loadData, 60000) // Refresh every 60s
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.heartbeat-widget {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.heartbeat-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.heart-icon {
  color: var(--text-tertiary);
  transition: color 0.3s;
}

.heart-icon.active {
  color: var(--color-danger);
}

.status-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.status-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.status-dot.ok {
  background: var(--color-success);
}

.status-dot.error {
  background: var(--color-danger);
}

.status-dot.inactive,
.status-dot.idle {
  background: var(--text-tertiary);
}

.status-dot.loading {
  background: var(--color-warning);
  animation: pulse 1s infinite;
}

.status-text {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: monospace;
}

.metrics-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.metric {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

.metric-label {
  color: var(--text-tertiary);
  font-size: 10px;
  text-transform: uppercase;
}

.metric-bar {
  width: 30px;
  height: 3px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.metric-fill {
  height: 100%;
  background: var(--color-success);
  transition: width 0.3s;
}

.metric-fill.warning {
  background: var(--color-warning);
}

.metric-fill.danger {
  background: var(--color-danger);
}

.metric-value {
  color: var(--text-secondary);
  font-family: monospace;
  font-size: 11px;
}

.tasks-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.task-indicator {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  font-size: 10px;
}

.task-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-success);
}

.task-indicator.running .task-dot {
  background: var(--color-warning);
  animation: pulse 1s infinite;
}

.task-indicator.error .task-dot {
  background: var(--color-danger);
}

.task-name {
  color: var(--text-secondary);
  max-width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
