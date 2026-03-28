<template>
  <div class="model-config-card">
    <!-- Header with title and description -->
    <div class="card-header">
      <div class="header-content">
        <h4 class="card-title">{{ title }}</h4>
        <p v-if="description" class="card-description">{{ description }}</p>
      </div>
      <!-- Enable toggle -->
      <div v-if="showEnable" class="enable-toggle">
        <ToggleSwitch v-model="localConfig.enabled" @update:model-value="emitConfig" />
      </div>
    </div>

    <!-- Provider and Model selection -->
    <div v-if="showProviderModel" class="form-row">
      <div class="form-group">
        <label class="label">{{ $t('settings.models.provider') }}</label>
        <Select
          v-model="localConfig.provider"
          :options="providerOptions"
          :placeholder="$t('settings.models.selectProvider')"
          @update:model-value="emitConfig"
        />
      </div>
      <div class="form-group">
        <label class="label">{{ $t('settings.models.model') }}</label>
        <Input
          v-model="localConfig.model"
          type="text"
          :placeholder="modelPlaceholder"
          @blur="emitConfig"
        />
      </div>
    </div>

    <!-- API Configuration (if needed) -->
    <div v-if="needsApiConfig && showApiConfig" class="api-config">
      <div class="form-group">
        <label class="label">
          {{ $t('settings.models.apiKey') }}
          <span v-if="isLocalProvider" class="label-hint">({{ $t('common.optional') }})</span>
        </label>
        <Input
          v-model="localConfig.api_key"
          type="password"
          :placeholder="isLocalProvider ? $t('settings.models.apiKeyOptional') : $t('settings.models.apiKeyPlaceholder')"
          @blur="emitConfig"
        />
      </div>
      <div class="form-group">
        <label class="label">
          {{ $t('settings.models.apiBase') }}
          <span v-if="defaultApiBase" class="label-hint">({{ $t('common.optional') }})</span>
        </label>
        <Input
          v-model="localConfig.api_base"
          type="text"
          :placeholder="defaultApiBase || $t('settings.models.apiBasePlaceholder')"
          @blur="emitConfig"
        />
        <p v-if="defaultApiBase" class="hint">
          {{ $t('settings.models.defaultApiBase') }}: {{ defaultApiBase }}
        </p>
      </div>
    </div>

    <!-- Basic parameters -->
    <div v-if="showBasicParams" class="basic-params">
      <div class="form-group">
        <label class="label">
          {{ $t('settings.models.temperature') }}
          <span class="value">{{ localConfig.temperature }}</span>
        </label>
        <p class="help-text">{{ $t('settings.models.temperatureDesc') }}</p>
        <input
          v-model.number="localConfig.temperature"
          type="range"
          min="0"
          max="2"
          step="0.1"
          class="slider"
          @change="emitConfig"
        >
        <div class="slider-labels">
          <span>0</span>
          <span>1</span>
          <span>2</span>
        </div>
      </div>

      <div class="form-group">
        <label class="label">
          {{ $t('settings.models.maxTokens') }}
          <span class="value">{{ localConfig.max_tokens === 0 ? $t('settings.models.maxTokensAuto') : formatTokens(localConfig.max_tokens) }}</span>
        </label>
        <p class="help-text">{{ $t('settings.models.maxTokensDesc') }}</p>
        <input
          v-model.number="localConfig.max_tokens"
          type="range"
          min="0"
          :max="maxTokensLimit"
          step="256"
          class="slider"
          @change="emitConfig"
        >
        <div class="slider-labels">
          <span>{{ $t('settings.models.maxTokensAuto') }}</span>
          <span>{{ formatTokens(Math.floor(maxTokensLimit / 2)) }}</span>
          <span>{{ formatTokens(maxTokensLimit) }}</span>
        </div>
      </div>
    </div>

    <!-- Advanced parameters (collapsible) -->
    <div v-if="showAdvanced" class="advanced-params">
      <div class="collapsible-header" @click="advancedExpanded = !advancedExpanded">
        <span>{{ $t('settings.models.advancedParams') }}</span>
        <ChevronIcon :class="['chevron-icon', { expanded: advancedExpanded }]" />
      </div>
      <div v-if="advancedExpanded" class="json-editor-container">
        <textarea
          v-model="advancedJson"
          class="json-editor"
          rows="6"
          :placeholder="$t('settings.models.advancedParamsPlaceholder')"
        />
        <div class="quick-templates">
          <Button size="sm" variant="secondary" @click="applyTemplate('default')">
            {{ $t('settings.models.templates.default') }}
          </Button>
          <Button size="sm" variant="secondary" @click="applyTemplate('creative')">
            {{ $t('settings.models.templates.creative') }}
          </Button>
          <Button size="sm" variant="secondary" @click="applyTemplate('precise')">
            {{ $t('settings.models.templates.precise') }}
          </Button>
        </div>
        <p v-if="jsonError" class="error-message">{{ jsonError }}</p>
      </div>
    </div>

    <!-- Extra slot for special parameters -->
    <slot name="extra"></slot>

    <!-- Test button -->
    <div v-if="showTestButton" class="card-actions">
      <Button
        variant="secondary"
        :loading="testing"
        :disabled="!canTest"
        @click="handleTest"
      >
        {{ testing ? $t('common.testing') : $t('settings.models.testConnection') }}
      </Button>
    </div>

    <!-- Test result -->
    <div v-if="testResult" class="test-result" :class="testResult.success ? 'success' : 'error'">
      <component
        :is="testResult.success ? CheckCircleIcon : XCircleIcon"
        :size="16"
      />
      <span>{{ testResult.message }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ChevronDown as ChevronIcon,
  CheckCircle as CheckCircleIcon,
  XCircle as XCircleIcon
} from 'lucide-vue-next'
import Input from '@/components/ui/Input.vue'
import Select from '@/components/ui/Select.vue'
import Button from '@/components/ui/Button.vue'
import ToggleSwitch from '@/components/ui/ToggleSwitch.vue'
import { settingsAPI } from '@/api'
import type { ProviderMetadata } from '@/types/settings'

export interface BaseModelConfig {
  enabled?: boolean
  provider: string
  model: string
  api_key?: string
  api_base?: string
  temperature: number
  max_tokens: number
  advanced_params?: Record<string, any>
}

interface Props {
  title: string
  description?: string
  config: BaseModelConfig
  providers?: ProviderMetadata[]
  showEnable?: boolean
  showAdvanced?: boolean
  showBasicParams?: boolean
  showProviderModel?: boolean
  showApiConfig?: boolean
  showTestButton?: boolean
  needsApiConfig?: boolean
  modelPlaceholder?: string
  maxTokensLimit?: number
}

const props = withDefaults(defineProps<Props>(), {
  showEnable: false,
  showAdvanced: true,
  showBasicParams: true,
  showProviderModel: true,
  showApiConfig: true,
  showTestButton: true,
  needsApiConfig: true,
  modelPlaceholder: '',
  maxTokensLimit: 32768,
  providers: () => []
})

const emit = defineEmits<{
  'update:config': [config: BaseModelConfig]
  'test': [success: boolean]
}>()

const { t } = useI18n()

// Local config state
const localConfig = ref<BaseModelConfig>({
  enabled: true,
  provider: '',
  model: '',
  api_key: '',
  api_base: '',
  temperature: 0.7,
  max_tokens: 4096,
  advanced_params: {}
})

// Advanced params state
const advancedExpanded = ref(false)
const advancedJson = ref('{}')
const jsonError = ref('')

// Test connection state
const testing = ref(false)
const testResult = ref<{ success: boolean; message: string } | null>(null)

// Available providers
const availableProviders = ref<ProviderMetadata[]>([])

// Load providers if not provided
onMounted(async () => {
  if (props.providers.length === 0) {
    try {
      availableProviders.value = await settingsAPI.getProviders()
    } catch (error) {
      console.error('Failed to load providers:', error)
    }
  }
})

// Provider options for select
const providerOptions = computed(() => {
  const providers = props.providers.length > 0 ? props.providers : availableProviders.value
  return providers.map(p => ({
    value: p.id,
    label: t(`settings.providers.${p.id}`, p.name)
  }))
})

// Local provider check (no API key required)
const LOCAL_PROVIDERS = ['ollama', 'vllm', 'lm_studio']
const isLocalProvider = computed(() => LOCAL_PROVIDERS.includes(localConfig.value.provider))

// Default API base for selected provider
const defaultApiBase = computed(() => {
  if (!localConfig.value.provider) return ''
  const providers = props.providers.length > 0 ? props.providers : availableProviders.value
  const providerMeta = providers.find(p => p.id === localConfig.value.provider)
  return providerMeta?.defaultApiBase || providerMeta?.default_api_base || ''
})

// Can test connection
const canTest = computed(() => {
  if (!localConfig.value.provider || !localConfig.value.model) return false
  if (!isLocalProvider.value && !localConfig.value.api_key) return false
  return true
})

// Initialize from props
watch(() => props.config, (newConfig) => {
  if (newConfig) {
    localConfig.value = {
      enabled: newConfig.enabled ?? true,
      provider: newConfig.provider ?? '',
      model: newConfig.model ?? '',
      api_key: newConfig.api_key ?? '',
      api_base: newConfig.api_base ?? '',
      temperature: newConfig.temperature ?? 0.7,
      max_tokens: newConfig.max_tokens ?? 4096,
      advanced_params: newConfig.advanced_params ?? {}
    }
    // Update JSON editor
    advancedJson.value = JSON.stringify(localConfig.value.advanced_params || {}, null, 2)
  }
}, { immediate: true })

// Sync local changes to parent - without deep watch to prevent loops
// Only emit on explicit user actions, not on every reactive change
const emitConfig = () => {
  emit('update:config', { ...localConfig.value })
}

// Watch JSON editor changes
watch(advancedJson, (newJson) => {
  try {
    if (newJson.trim()) {
      const parsed = JSON.parse(newJson)
      localConfig.value.advanced_params = parsed
      jsonError.value = ''
      // Emit config change after successful JSON parse
      emitConfig()
    }
  } catch (e) {
    jsonError.value = t('settings.models.invalidJson')
  }
})

// Format tokens display
const formatTokens = (tokens: number): string => {
  if (tokens >= 1000) {
    return `${Math.round(tokens / 1000)}K`
  }
  return String(tokens)
}

// Apply template for advanced params
const applyTemplate = (template: string) => {
  const templates: Record<string, Record<string, any>> = {
    default: {
      top_p: 0.9,
      frequency_penalty: 0.0,
      presence_penalty: 0.0
    },
    creative: {
      top_p: 0.95,
      temperature: 0.9,
      frequency_penalty: 0.5,
      presence_penalty: 0.5
    },
    precise: {
      top_p: 0.7,
      temperature: 0.3,
      frequency_penalty: 0.0,
      presence_penalty: 0.0
    }
  }

  const selected = templates[template] || templates.default
  advancedJson.value = JSON.stringify(selected, null, 2)
}

// Test connection handler
const handleTest = async () => {
  if (!canTest.value) return

  testing.value = true
  testResult.value = null

  // Debug: log what we're sending
  console.log('[ModelConfigCard] Test connection request:', {
    provider: localConfig.value.provider,
    api_key: localConfig.value.api_key ? '(masked)' : '(empty)',
    api_base: localConfig.value.api_base,
    model: localConfig.value.model
  })

  try {
    const response = await settingsAPI.testConnection({
      provider: localConfig.value.provider,
      api_key: localConfig.value.api_key || '',
      api_base: localConfig.value.api_base,
      model: localConfig.value.model
    })

    testResult.value = {
      success: response.success,
      message: response.success
        ? (response.message || t('settings.models.testSuccess'))
        : (response.error || response.message || t('settings.models.testFailed'))
    }
    emit('test', response.success)
  } catch (error: any) {
    testResult.value = {
      success: false,
      message: error.response?.data?.error || error.message || t('settings.models.testFailed')
    }
    emit('test', false)
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.model-config-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.header-content {
  flex: 1;
}

.card-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.card-description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: var(--spacing-xs) 0 0;
}

.enable-toggle {
  flex-shrink: 0;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

@media (max-width: 640px) {
  .form-row {
    grid-template-columns: 1fr;
  }
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.label-hint {
  font-weight: var(--font-weight-normal);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.value {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.hint {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin: 0;
}

.help-text {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin: 0;
  line-height: 1.5;
}

.slider {
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-tertiary);
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  transition: all var(--transition-base);
}

.slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.2);
}

.slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  border: none;
  transition: all var(--transition-base);
}

.slider::-moz-range-thumb:hover {
  transform: scale(1.2);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.2);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}

.api-config {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.basic-params {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.advanced-params {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.collapsible-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  transition: background var(--transition-base);
}

.collapsible-header:hover {
  background: var(--bg-hover);
}

.chevron-icon {
  transition: transform var(--transition-base);
}

.chevron-icon.expanded {
  transform: rotate(180deg);
}

.json-editor-container {
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.json-editor {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
  resize: vertical;
}

.json-editor:focus {
  outline: none;
  border-color: var(--color-primary);
}

.quick-templates {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.error-message {
  font-size: var(--font-size-xs);
  color: var(--color-error);
  margin: 0;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
}

.test-result {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}

.test-result.success {
  background: rgba(16, 185, 129, 0.1);
  color: var(--color-success);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.test-result.error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-error);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.test-result span {
  flex: 1;
  word-break: break-word;
}
</style>
