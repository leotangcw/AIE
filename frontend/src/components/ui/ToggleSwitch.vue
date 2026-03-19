<template>
  <label class="toggle-switch">
    <input
      type="checkbox"
      :checked="modelValue"
      @change="handleChange"
    />
    <span class="toggle-slider"></span>
  </label>
</template>

<script setup lang="ts">
interface Props {
  modelValue: boolean
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const handleChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.checked)
}
</script>

<style scoped>
/* Toggle Switch */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
  cursor: pointer;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--color-border-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  transition: all var(--transition-base);
}

.toggle-slider:before {
  content: '';
  position: absolute;
  height: 18px;
  width: 18px;
  left: 2px;
  bottom: 2px;
  background-color: white;
  border-radius: 50%;
  transition: all var(--transition-base);
  box-shadow: var(--shadow-sm);
}

.toggle-switch input:checked + .toggle-slider {
  background-color: var(--color-success, #10b981);
  border-color: var(--color-success, #10b981);
}

.toggle-switch input:checked + .toggle-slider:before {
  transform: translateX(20px);
}

.toggle-switch:hover .toggle-slider {
  opacity: 0.9;
}

/* 深色模式开关 */
:root[data-theme="dark"] .toggle-slider {
  background-color: #1e2d45;
  border-color: #243050;
}

:root[data-theme="dark"] .toggle-slider:before {
  background-color: #7a9ab0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
}

:root[data-theme="dark"] .toggle-switch input:checked + .toggle-slider {
  background-color: rgba(0, 240, 255, 0.15);
  border-color: #00f0ff;
}

:root[data-theme="dark"] .toggle-switch input:checked + .toggle-slider:before {
  background-color: #00f0ff;
  box-shadow: 0 0 6px rgba(0, 240, 255, 0.3);
}
</style>
