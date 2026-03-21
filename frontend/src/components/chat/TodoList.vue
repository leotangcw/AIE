<template>
  <div class="todo-list-container">
    <div class="todo-list-header">
      <component
        :is="ListTodoIcon"
        :size="16"
        class="todo-icon"
      />
      <span class="todo-title">{{ $t('todo.title') || '待办事项' }}</span>
      <span class="todo-count">{{ todos.length }}</span>
    </div>
    <div class="todo-items" :class="{ 'has-scroll': todos.length > 4 }">
      <div
        v-for="(todo, index) in todos"
        :key="todo.id"
        class="todo-item"
        :class="`status-${todo.status}`"
      >
        <span class="todo-checkbox">
          {{ getStatusIcon(todo.status) }}
        </span>
        <span class="todo-content">{{ todo.content }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ListTodo as ListTodoIcon } from 'lucide-vue-next'

export interface TodoItem {
  id: string
  content: string
  activeForm?: string
  status: 'pending' | 'in_progress' | 'completed'
  createdAt?: string
  updatedAt?: string
}

interface Props {
  todos: TodoItem[]
}

defineProps<Props>()

const getStatusIcon = (status: string): string => {
  const iconMap: Record<string, string> = {
    pending: '○',
    in_progress: '◐',
    completed: '●'
  }
  return iconMap[status] || '○'
}
</script>

<style scoped>
.todo-list-container {
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-primary, #ffffff);
  margin: var(--spacing-sm) 0;
}

.todo-list-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary, #f8fafc);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}

.todo-icon {
  color: var(--text-tertiary, #94a3b8);
}

.todo-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #475569);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.todo-count {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary, #94a3b8);
  background: var(--bg-tertiary, #f1f5f9);
  padding: 1px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.todo-items {
  display: flex;
  flex-direction: column;
  max-height: 160px;
  overflow-y: auto;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
  transition: background 0.1s ease;
}

.todo-item:last-child {
  border-bottom: none;
}

.todo-item:hover {
  background: var(--hover-bg, #f8fafc);
}

.todo-item.status-completed .todo-content {
  text-decoration: line-through;
  color: var(--text-tertiary, #94a3b8);
}

.todo-item.status-in_progress {
  background: rgba(59, 130, 246, 0.05);
}

.todo-checkbox {
  font-size: 14px;
  width: 20px;
  text-align: center;
  color: var(--text-tertiary, #94a3b8);
}

.todo-item.status-completed .todo-checkbox {
  color: #22C55E;
}

.todo-item.status-in_progress .todo-checkbox {
  color: #3B82F6;
}

.todo-content {
  font-size: 13px;
  color: var(--text-primary, #1e293b);
  flex: 1;
}

.todo-empty {
  padding: 16px;
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary, #94a3b8);
}

/* Dark mode */
:root[data-theme='dark'] .todo-list-container {
  border-color: var(--border-color, #152035);
}

:root[data-theme='dark'] .todo-list-header {
  background: rgba(14, 20, 34, 0.8);
  border-color: var(--border-color, #152035);
}

:root[data-theme='dark'] .todo-item {
  border-color: rgba(21, 32, 53, 0.8);
}

:root[data-theme='dark'] .todo-item:hover {
  background: rgba(14, 20, 34, 0.5);
}

:root[data-theme='dark'] .todo-item.status-in_progress {
  background: rgba(59, 130, 246, 0.1);
}
</style>
