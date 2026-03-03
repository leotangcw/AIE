<template>
  <div class="rules-config">
    <div class="section-header">
      <h3 class="section-title">{{ $t('settings.rules.title') }}</h3>
      <p class="section-desc">{{ $t('settings.rules.description') }}</p>
    </div>

    <!-- 规则列表 -->
    <div class="rules-list">
      <div class="list-header">
        <span class="header-title">{{ $t('settings.rules.rulesList') }}</span>
        <button class="add-btn" @click="showCreateDialog = true">
          <component :is="PlusIcon" :size="16" />
          {{ $t('settings.rules.addRule') }}
        </button>
      </div>

      <!-- 规则项 -->
      <div v-if="rules.length === 0" class="empty-state">
        <component :is="FileTextIcon" :size="48" class="empty-icon" />
        <p>{{ $t('settings.rules.empty') }}</p>
      </div>

      <div v-else class="rules-grid">
        <div
          v-for="rule in rules"
          :key="rule.id"
          class="rule-card"
          :class="{ disabled: !rule.enabled }"
        >
          <div class="rule-header">
            <div class="rule-info">
              <h4 class="rule-name">{{ rule.name }}</h4>
              <p class="rule-desc">{{ rule.description }}</p>
            </div>
            <label class="toggle-switch">
              <input
                v-model="rule.enabled"
                type="checkbox"
                @change="toggleRule(rule)"
              >
              <span class="toggle-slider"></span>
            </label>
          </div>

          <div class="rule-body">
            <div class="rule-condition">
              <span class="label">{{ $t('settings.rules.condition') }}:</span>
              <code>{{ rule.condition }}</code>
            </div>
            <div class="rule-action">
              <span class="label">{{ $t('settings.rules.action') }}:</span>
              <code>{{ rule.action }}</code>
            </div>
          </div>

          <div class="rule-footer">
            <span class="priority-badge">{{ $t('settings.rules.priority') }}: {{ rule.priority }}</span>
            <div class="actions">
              <button class="action-btn" @click="editRule(rule)" :title="$t('common.edit')">
                <component :is="EditIcon" :size="16" />
              </button>
              <button class="action-btn danger" @click="deleteRule(rule.id)" :title="$t('common.delete')">
                <component :is="TrashIcon" :size="16" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 创建/编辑对话框 -->
    <div v-if="showCreateDialog || editingRule" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog">
        <div class="dialog-header">
          <h3>{{ editingRule ? $t('settings.rules.editRule') : $t('settings.rules.createRule') }}</h3>
          <button class="close-btn" @click="closeDialog">
            <component :is="XIcon" :size="20" />
          </button>
        </div>

        <div class="dialog-body">
          <div class="form-group">
            <label>{{ $t('settings.rules.ruleName') }}</label>
            <input v-model="formData.name" type="text" :placeholder="$t('settings.rules.namePlaceholder')" />
          </div>

          <div class="form-group">
            <label>{{ $t('settings.rules.ruleDescription') }}</label>
            <input v-model="formData.description" type="text" :placeholder="$t('settings.rules.descPlaceholder')" />
          </div>

          <div class="form-group">
            <label>{{ $t('settings.rules.condition') }}</label>
            <textarea v-model="formData.condition" rows="3" :placeholder="$t('settings.rules.conditionPlaceholder')"></textarea>
          </div>

          <div class="form-group">
            <label>{{ $t('settings.rules.action') }}</label>
            <textarea v-model="formData.action" rows="3" :placeholder="$t('settings.rules.actionPlaceholder')"></textarea>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>{{ $t('settings.rules.priority') }}</label>
              <input v-model.number="formData.priority" type="number" min="0" max="100" />
            </div>
            <div class="form-group">
              <label class="checkbox-label">
                <input v-model="formData.enabled" type="checkbox" />
                {{ $t('settings.rules.enabled') }}
              </label>
            </div>
          </div>
        </div>

        <div class="dialog-footer">
          <button class="btn secondary" @click="closeDialog">{{ $t('common.cancel') }}</button>
          <button class="btn primary" @click="saveRule">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Plus as PlusIcon,
  FileText as FileTextIcon,
  Edit as EditIcon,
  Trash as TrashIcon,
  X as XIcon
} from 'lucide-vue-next'
import rulesApi, { type Rule, type RuleCreate } from '@/api/rules'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const toast = useToast()

const rules = ref<Rule[]>([])
const showCreateDialog = ref(false)
const editingRule = ref<Rule | null>(null)

const formData = ref<RuleCreate>({
  name: '',
  description: '',
  condition: '',
  action: '',
  enabled: true,
  priority: 50
})

const loadRules = async () => {
  try {
    rules.value = await rulesApi.getRules()
  } catch (error) {
    console.error('Failed to load rules:', error)
    toast.error(t('settings.rules.loadError'))
  }
}

const toggleRule = async (rule: Rule) => {
  try {
    await rulesApi.toggleRule(rule.id, rule.enabled)
    toast.success(t('settings.rules.toggleSuccess'))
  } catch (error) {
    console.error('Failed to toggle rule:', error)
    rule.enabled = !rule.enabled
    toast.error(t('settings.rules.toggleError'))
  }
}

const editRule = (rule: Rule) => {
  editingRule.value = rule
  formData.value = {
    name: rule.name,
    description: rule.description,
    condition: rule.condition,
    action: rule.action,
    enabled: rule.enabled,
    priority: rule.priority
  }
}

const deleteRule = async (id: string) => {
  if (!confirm(t('settings.rules.confirmDelete'))) return

  try {
    await rulesApi.deleteRule(id)
    rules.value = rules.value.filter(r => r.id !== id)
    toast.success(t('settings.rules.deleteSuccess'))
  } catch (error) {
    console.error('Failed to delete rule:', error)
    toast.error(t('settings.rules.deleteError'))
  }
}

const closeDialog = () => {
  showCreateDialog.value = false
  editingRule.value = null
  formData.value = {
    name: '',
    description: '',
    condition: '',
    action: '',
    enabled: true,
    priority: 50
  }
}

const saveRule = async () => {
  try {
    if (editingRule.value) {
      await rulesApi.updateRule(editingRule.value.id, formData.value)
      toast.success(t('settings.rules.updateSuccess'))
    } else {
      await rulesApi.createRule(formData.value)
      toast.success(t('settings.rules.createSuccess'))
    }
    await loadRules()
    closeDialog()
  } catch (error) {
    console.error('Failed to save rule:', error)
    toast.error(t('settings.rules.saveError'))
  }
}

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.rules-config {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
  padding: var(--spacing-md);
}

.section-header {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0;
}

.section-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: 0;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-md);
}

.header-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.add-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 8px 16px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-base);
}

.add-btn:hover {
  background: var(--color-primary-hover);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xxl);
  color: var(--color-text-tertiary);
}

.empty-icon {
  margin-bottom: var(--spacing-md);
  opacity: 0.5;
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: var(--spacing-md);
}

.rule-card {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: all var(--transition-base);
}

.rule-card:hover {
  border-color: var(--color-border-secondary);
  box-shadow: var(--shadow-sm);
}

.rule-card.disabled {
  opacity: 0.6;
}

.rule-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--color-border-primary);
}

.rule-info {
  flex: 1;
  min-width: 0;
}

.rule-name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-xs) 0;
}

.rule-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: 0;
}

.rule-body {
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.rule-condition,
.rule-action {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-tertiary);
  text-transform: uppercase;
}

.rule-body code {
  font-size: var(--font-size-xs);
  font-family: var(--font-family-mono);
  background: var(--color-bg-tertiary);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
}

.rule-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-secondary);
  border-top: 1px solid var(--color-border-primary);
}

.priority-badge {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.actions {
  display: flex;
  gap: var(--spacing-xs);
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-base);
}

.action-btn:hover {
  background: var(--color-bg-tertiary);
  border-color: var(--color-border-secondary);
  color: var(--color-text-primary);
}

.action-btn.danger:hover {
  background: var(--color-error-light);
  border-color: var(--color-error);
  color: var(--color-error);
}

/* Dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--spacing-md);
}

.dialog {
  background: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow: auto;
  box-shadow: var(--shadow-lg);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--color-border-primary);
}

.dialog-header h3 {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  margin: 0;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  background: transparent;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.dialog-body {
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-group label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.form-group input,
.form-group textarea {
  padding: 10px 12px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  transition: all var(--transition-base);
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--color-primary);
}

.form-row {
  display: flex;
  gap: var(--spacing-md);
}

.form-row .form-group {
  flex: 1;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
}

.checkbox-label input {
  width: auto;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg);
  border-top: 1px solid var(--color-border-primary);
}

.btn {
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-base);
}

.btn.secondary {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
  color: var(--color-text-primary);
}

.btn.primary {
  background: var(--color-primary);
  border: none;
  color: white;
}

.btn.primary:hover {
  background: var(--color-primary-hover);
}

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
</style>
