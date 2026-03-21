<template>
  <transition name="slide-up">
    <div v-if="visible" class="subtask-progress">
      <div class="progress-indicator">
        <div class="progress-spinner">
          <div class="spinner-ring" />
        </div>
        <div class="progress-info">
          <div class="progress-description">
            <span v-if="status === 'starting'" class="status-starting">
              {{ $t('subtask.starting') || '准备执行...' }}
            </span>
            <span v-else-if="status === 'tool_call'" class="status-tool">
              <component
                :is="WrenchIcon"
                :size="12"
                class="tool-icon"
              />
              {{ toolName || '执行中' }}
            </span>
            <span v-else-if="status === 'tool_result'" class="status-result">
              <component
                :is="CheckIcon"
                :size="12"
                class="result-icon"
              />
              {{ toolName || '完成' }}
            </span>
            <span v-else-if="status === 'completed'" class="status-completed">
              <component
                :is="CheckCircleIcon"
                :size="12"
                class="completed-icon"
              />
              {{ $t('subtask.completed') || '任务完成' }}
            </span>
            <span v-else-if="status === 'error'" class="status-error">
              <component
                :is="XCircleIcon"
                :size="12"
                class="error-icon"
              />
              {{ $t('subtask.error') || '执行出错' }}
            </span>
            <span v-else class="status-default">
              {{ description }}
            </span>
          </div>
          <div v-if="message" class="progress-message">
            {{ message }}
          </div>
          <div v-if="toolCount > 0" class="progress-stats">
            <span class="tool-count">
              {{ current }}/{{ total || toolCount }}
            </span>
            <span v-if="isParallel" class="parallel-badge">
              {{ $t('subtask.parallel') || '并行' }}
            </span>
          </div>
        </div>
      </div>
      <div v-if="showProgress" class="progress-bar-container">
        <div
          class="progress-bar"
          :class="progressClass"
          :style="{ width: `${progressPercent}%` }"
        />
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import {
  Wrench as WrenchIcon,
  Check as CheckIcon,
  CheckCircle as CheckCircleIcon,
  XCircle as XCircleIcon
} from 'lucide-vue-next'
import { computed } from 'vue'

interface Props {
  taskId?: string
  description?: string
  status?: 'starting' | 'tool_call' | 'tool_result' | 'completed' | 'error'
  toolName?: string
  toolCount?: number
  current?: number
  total?: number
  isParallel?: boolean
  message?: string
}

const props = withDefaults(defineProps<Props>(), {
  taskId: '',
  description: '',
  status: 'starting',
  toolName: '',
  toolCount: 0,
  current: 0,
  total: 0,
  isParallel: false,
  message: ''
})

const visible = computed(() => {
  return props.status !== 'completed' && props.status !== 'error'
})

const showProgress = computed(() => {
  return props.total > 0 && props.current >= 0
})

const progressPercent = computed(() => {
  if (!props.total || props.total === 0) return 0
  return Math.min(100, Math.max(0, (props.current / props.total) * 100))
})

const progressClass = computed(() => {
  if (props.status === 'error') return 'progress-error'
  if (props.status === 'completed') return 'progress-completed'
  return ''
})
</script>

<style scoped>
.subtask-progress {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(59, 130, 246, 0.02));
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 10px;
  margin: var(--spacing-xs) 0;
  max-width: 400px;
}

.progress-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-spinner {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner-ring {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3B82F6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.progress-info {
  flex: 1;
  min-width: 0;
}

.progress-description {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #1e293b);
  display: flex;
  align-items: center;
  gap: 6px;
}

.progress-message {
  font-size: 12px;
  color: var(--text-secondary, #64748b);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.tool-count {
  font-size: 11px;
  font-weight: 600;
  color: #3B82F6;
  background: rgba(59, 130, 246, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
}

.parallel-badge {
  font-size: 10px;
  font-weight: 500;
  color: #8B5CF6;
  background: rgba(139, 92, 246, 0.1);
  padding: 1px 6px;
  border-radius: 4px;
  text-transform: uppercase;
}

.tool-icon {
  color: #3B82F6;
}

.result-icon {
  color: #22C55E;
}

.completed-icon {
  color: #22C55E;
}

.error-icon {
  color: #EF4444;
}

.status-tool,
.status-starting {
  color: #3B82F6;
}

.status-result,
.status-completed {
  color: #22C55E;
}

.status-error {
  color: #EF4444;
}

.progress-bar-container {
  height: 3px;
  background: rgba(59, 130, 246, 0.15);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #3B82F6, #60A5FA);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-bar.progress-error {
  background: linear-gradient(90deg, #EF4444, #F87171);
}

.progress-bar.progress-completed {
  background: linear-gradient(90deg, #22C55E, #4ADE80);
}

/* Slide up animation */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.25s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

/* Dark mode */
:root[data-theme='dark'] .subtask-progress {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(59, 130, 246, 0.05));
  border-color: rgba(59, 130, 246, 0.3);
}

:root[data-theme='dark'] .spinner-ring {
  border-color: rgba(59, 130, 246, 0.3);
  border-top-color: #60A5FA;
}

:root[data-theme='dark'] .progress-description {
  color: #E2E8F0;
}

:root[data-theme='dark'] .progress-message {
  color: #94A3B8;
}

:root[data-theme='dark'] .tool-count {
  color: #60A5FA;
  background: rgba(59, 130, 246, 0.2);
}

:root[data-theme='dark'] .parallel-badge {
  color: #A78BFA;
  background: rgba(139, 92, 246, 0.2);
}
</style>
