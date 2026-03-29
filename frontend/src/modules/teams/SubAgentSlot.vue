<template>
  <div class="sub-agent-slot">
    <!-- Header -->
    <div class="slot-header">
      <div class="slot-header-left">
        <span
          class="status-dot"
          :class="`status-${agent.status}`"
        />
        <span class="agent-role">{{ agent.role }}</span>
        <span class="agent-task" :title="agent.task">{{ truncate(agent.task, 40) }}</span>
      </div>
      <div class="slot-header-right">
        <span v-if="agent.tool_count > 0" class="tool-badge" :title="`共 ${agent.tool_count} 次工具调用`">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
          {{ agent.tool_count }} 次调用
        </span>
        <span class="status-label" :class="`status-label-${agent.status}`">{{ statusLabel }}</span>
        <span v-if="agent.duration > 0" class="duration-badge">{{ formatDuration(agent.duration) }}</span>
      </div>
    </div>

    <!-- Progress bar -->
    <div v-if="agent.status === 'running'" class="progress-bar">
      <div
        class="progress-fill"
        :style="{ width: `${Math.min(100, Math.max(0, agent.progress))}%` }"
      />
    </div>

    <!-- Messages area -->
    <div ref="messagesRef" class="slot-messages">
      <!-- Empty states per status -->
      <div v-if="agent.messages.length === 0" class="empty-state">
        <span v-if="agent.status === 'queued'">等待前序任务完成...</span>
        <span v-else-if="agent.status === 'running'">正在处理...</span>
        <span v-else-if="agent.status === 'waiting'">等待中...</span>
        <span v-else-if="agent.status === 'completed'">已完成</span>
        <span v-else-if="agent.status === 'error'">发生错误</span>
      </div>

      <!-- Message list -->
      <template v-else>
        <template v-for="(msg, idx) in agent.messages" :key="idx">
          <!-- Tool message → 使用 ToolCallCard 组件 -->
          <ToolCallCard
            v-if="msg.role === 'tool'"
            :tool-name="msg.tool_name || 'Tool'"
            :arguments="msg.arguments || {}"
            :status="msg.tool_result !== undefined ? 'success' : 'running'"
            :result="msg.tool_result"
            :default-collapsed="true"
            class="msg-tool-card"
          />

          <!-- System message -->
          <div v-else-if="msg.role === 'system'" class="msg-item">
            <div class="msg-content msg-system">{{ msg.content }}</div>
          </div>

          <!-- Assistant message -->
          <div v-else-if="msg.role === 'assistant'" class="msg-item">
            <div v-if="msg.is_thinking" class="msg-content msg-thinking">{{ msg.content }}</div>
            <div v-else class="msg-content msg-assistant">{{ msg.content }}</div>
          </div>

          <!-- User message -->
          <div v-else class="msg-item">
            <div class="msg-content msg-user">{{ msg.content }}</div>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { SubAgentState } from '@/store/teams'
import ToolCallCard from '@/components/chat/ToolCallCard.vue'

const props = defineProps<{
  agent: SubAgentState
}>()

const messagesRef = ref<HTMLElement | null>(null)

const statusLabels: Record<string, string> = {
  queued: '排队中',
  running: '运行中',
  waiting: '等待中',
  completed: '已完成',
  error: '错误',
}

const statusLabel = computed(() => statusLabels[props.agent.status] || props.agent.status)

function truncate(text: string, max: number): string {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs}s`
}

function autoScroll() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

watch(() => props.agent.messages.length, () => {
  autoScroll()
})
</script>

<style scoped>
.sub-agent-slot {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary, #1a1a2e);
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 6px;
  overflow: hidden;
}

/* Header */
.slot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--bg-secondary, #16162a);
  border-bottom: 1px solid var(--border-color, #2a2a3a);
  flex-shrink: 0;
  gap: 8px;
  min-height: 32px;
}

.slot-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}

.slot-header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.status-queued {
  background: var(--text-tertiary, #666);
}

.status-dot.status-running {
  background: #4f8ff7;
  animation: pulse 1.5s infinite;
}

.status-dot.status-waiting {
  background: #f0ad4e;
}

.status-dot.status-completed {
  background: #5cb85c;
}

.status-dot.status-error {
  background: #d9534f;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.agent-role {
  font-weight: 600;
  font-size: 12px;
  color: var(--text-primary, #e0e0e0);
  white-space: nowrap;
}

.agent-task {
  font-size: 11px;
  color: var(--text-tertiary, #888);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: var(--accent-color, #4f8ff7);
  background: rgba(79, 143, 247, 0.1);
  padding: 1px 5px;
  border-radius: 4px;
  white-space: nowrap;
}

.status-label {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
}

.status-label-queued {
  color: var(--text-tertiary, #888);
  background: rgba(136, 136, 136, 0.15);
}

.status-label-running {
  color: #4f8ff7;
  background: rgba(79, 143, 247, 0.15);
}

.status-label-waiting {
  color: #f0ad4e;
  background: rgba(240, 173, 78, 0.15);
}

.status-label-completed {
  color: #5cb85c;
  background: rgba(92, 184, 92, 0.15);
}

.status-label-error {
  color: #d9534f;
  background: rgba(217, 83, 79, 0.15);
}

.duration-badge {
  font-size: 10px;
  color: var(--text-tertiary, #888);
}

/* Progress bar */
.progress-bar {
  height: 2px;
  background: var(--border-color, #2a2a3a);
  flex-shrink: 0;
}

.progress-fill {
  height: 100%;
  background: var(--accent-color, #4f8ff7);
  transition: width 0.3s ease;
  border-radius: 1px;
}

/* Messages area */
.slot-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  font-size: 12px;
  line-height: 1.5;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary, #888);
  font-style: italic;
  font-size: 12px;
}

/* Message items */
.msg-item {
  margin-bottom: 6px;
  padding: 4px 6px;
  border-radius: 4px;
}

/* ToolCallCard 容器 — 紧凑间距 */
.msg-tool-card {
  margin-bottom: 6px;
}

.msg-tool-card :deep(.tool-header) {
  padding: 4px 8px;
}

.msg-tool-card :deep(.tool-name) {
  font-size: 11px;
}

.msg-tool-card :deep(.tool-result) {
  max-height: 150px;
  font-size: 11px;
}

.msg-content {
  color: var(--text-primary, #e0e0e0);
  word-break: break-word;
  white-space: pre-wrap;
}

.msg-system {
  color: var(--text-tertiary, #888);
  font-style: italic;
}

.msg-thinking {
  color: var(--text-tertiary, #888);
  font-style: italic;
}

.msg-assistant {
  color: var(--text-primary, #e0e0e0);
}

.msg-user {
  color: var(--text-secondary, #bbb);
}

/* Scrollbar styling */
.slot-messages::-webkit-scrollbar {
  width: 4px;
}

.slot-messages::-webkit-scrollbar-track {
  background: transparent;
}

.slot-messages::-webkit-scrollbar-thumb {
  background: var(--border-color, #2a2a3a);
  border-radius: 2px;
}
</style>
