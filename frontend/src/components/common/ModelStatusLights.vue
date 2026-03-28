<template>
  <div class="model-status-lights">
    <div
      v-for="(info, role) in models"
      :key="role"
      class="model-indicator"
      :class="statusClass(info)"
      :title="tooltipText(role, info)"
    >
      <span class="status-dot" />
      <span class="model-name">{{ info.model_name || role }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
interface ModelInfo {
  healthy: boolean
  model_name: string
  last_success?: string | null
  last_failure?: string | null
  consecutive_failures?: number
}

const props = withDefaults(defineProps<{
  models: Record<string, ModelInfo>
}>(), {
  models: () => ({
    main: { healthy: true, model_name: '', consecutive_failures: 0 },
    sub: { healthy: true, model_name: '', consecutive_failures: 0 },
  }),
})

const roleLabels: Record<string, string> = {
  main: '主模型',
  sub: '子模型',
}

function statusClass(info: ModelInfo): string {
  if (info.healthy) return 'status-healthy'
  if ((info.consecutive_failures || 0) > 0) return 'status-degraded'
  return 'status-unhealthy'
}

function tooltipText(role: string, info: ModelInfo): string {
  const label = roleLabels[role] || role
  const name = info.model_name || role
  let text = `${label}: ${name}`
  if (info.last_failure) {
    text += ` | 上次失败: ${formatTime(info.last_failure)}`
  }
  if (info.consecutive_failures && info.consecutive_failures > 0) {
    text += ` | 连续失败: ${info.consecutive_failures}次`
  }
  return text
}

function formatTime(iso?: string | null): string {
  if (!iso) return 'N/A'
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString()
  } catch {
    return iso
  }
}
</script>

<style scoped>
.model-status-lights {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}

.model-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #64748b);
  cursor: default;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-healthy .status-dot {
  background: #22C55E;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.status-degraded .status-dot {
  background: #F59E0B;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
}

.status-unhealthy .status-dot {
  background: #EF4444;
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.5);
  animation: pulse-red 2s ease-in-out infinite;
}

.model-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes pulse-red {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

:root[data-theme='dark'] .model-indicator {
  color: #94A3B8;
}
</style>
