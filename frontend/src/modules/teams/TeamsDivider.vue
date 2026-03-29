<template>
  <div
    class="teams-divider"
    :class="{ dragging: isDragging }"
    @mousedown="onMouseDown"
  >
    <div class="divider-line" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  modelValue: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const isDragging = ref(false)

function clampRatio(value: number): number {
  return Math.min(0.7, Math.max(0.3, value))
}

function onMouseDown(e: MouseEvent) {
  e.preventDefault()
  isDragging.value = true

  const container = document.querySelector('.chat-pane') as HTMLElement | null
  if (!container) {
    isDragging.value = false
    return
  }

  const containerRect = container.getBoundingClientRect()

  function onMouseMove(ev: MouseEvent) {
    const x = ev.clientX - containerRect.left
    let ratio = x / containerRect.width
    ratio = clampRatio(ratio)
    // Round to 2 decimal places for cleanliness
    ratio = Math.round(ratio * 100) / 100
    emit('update:modelValue', ratio)
  }

  function onMouseUp() {
    isDragging.value = false
    const ratio = clampRatio(props.modelValue)
    localStorage.setItem('aie-teams-split-ratio', String(ratio))
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}
</script>

<style scoped>
.teams-divider {
  width: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: col-resize;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
  transition: background-color 0.15s ease;
}

.teams-divider:hover,
.teams-divider.dragging {
  background-color: var(--accent-color, #4f8ff7);
}

.divider-line {
  width: 2px;
  height: 100%;
  background-color: var(--border-color, #2a2a3a);
  pointer-events: none;
}

.teams-divider:hover .divider-line,
.teams-divider.dragging .divider-line {
  background-color: transparent;
}
</style>
