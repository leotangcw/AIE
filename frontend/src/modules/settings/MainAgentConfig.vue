<template>
  <div class="main-agent-config">
    <ModelConfigCard
      :title="$t('settings.models.mainAgent.title')"
      :description="$t('settings.models.mainAgent.description')"
      v-model:config="mainAgentConfig"
      :providers="providers"
      :show-enable="false"
      :show-advanced="true"
      :show-test-button="true"
      :needs-api-config="true"
      :max-tokens-limit="128000"
      :model-placeholder="$t('settings.models.mainAgent.modelPlaceholder')"
      @test="handleTest"
    >
      <template #extra>
        <!-- Main Agent specific parameters -->
        <div class="extra-params">
          <div class="form-group">
            <label class="label">
              {{ $t('settings.models.maxIterations') }}
              <span class="value">{{ mainAgentConfig.max_iterations }}</span>
            </label>
            <p class="help-text">{{ $t('settings.models.maxIterationsDesc') }}</p>
            <input
              v-model.number="mainAgentConfig.max_iterations"
              type="range"
              min="1"
              max="9999"
              step="1"
              class="slider"
            >
            <div class="slider-labels">
              <span>1</span>
              <span>5000</span>
              <span>9999 ({{ $t('settings.models.unlimited') }})</span>
            </div>
          </div>
        </div>
      </template>
    </ModelConfigCard>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import ModelConfigCard, { type BaseModelConfig } from './components/ModelConfigCard.vue'
import { useSettingsStore } from '@/store/settings'
import { settingsAPI } from '@/api'
import type { ProviderMetadata } from '@/types/settings'

interface MainAgentConfigData extends BaseModelConfig {
  max_iterations: number
}

const { t } = useI18n()
const settingsStore = useSettingsStore()

const providers = ref<ProviderMetadata[]>([])
// Use shallowRef for flags to prevent unnecessary reactivity
const isUpdating = shallowRef(false)
const isInitialized = shallowRef(false)

const mainAgentConfig = ref<MainAgentConfigData>({
  enabled: true,
  provider: 'qwen',
  model: 'qwen3.5-plus',
  api_key: '',
  api_base: '',
  temperature: 0.7,
  max_tokens: 4096,
  max_iterations: 9999,
  advanced_params: {}
})

// Load providers
onMounted(async () => {
  try {
    providers.value = await settingsAPI.getProviders()
  } catch (error) {
    console.error('Failed to load providers:', error)
  }
})

// Initialize from store
const initializeFromStore = () => {
  if (!settingsStore.settings?.model) {
    console.log('[MainAgentConfig] No model config in store yet')
    return false
  }

  const modelConfig = settingsStore.settings.model
  const providerId = modelConfig.provider || 'qwen'
  const providerConfig = settingsStore.settings.providers?.[providerId]

  console.log('[MainAgentConfig] providerId:', providerId)
  console.log('[MainAgentConfig] providerConfig:', providerConfig)
  console.log('[MainAgentConfig] providers from store:', settingsStore.settings.providers)

  mainAgentConfig.value = {
    enabled: true,
    provider: providerId,
    model: modelConfig.model || 'qwen3.5-plus',
    api_key: providerConfig?.api_key || '',
    api_base: providerConfig?.api_base || '',
    temperature: modelConfig.temperature ?? 0.7,
    max_tokens: modelConfig.max_tokens ?? 4096,
    max_iterations: modelConfig.max_iterations ?? 9999,
    advanced_params: {}
  }

  console.log('[MainAgentConfig] Initialized config:', mainAgentConfig.value)
  return true
}

// Initialize on mount
onMounted(() => {
  console.log('[MainAgentConfig] Mounting, settings:', settingsStore.settings)
  const initialized = initializeFromStore()

  // Mark as initialized after a tick to prevent immediate watch trigger
  setTimeout(() => {
    isInitialized.value = true
  }, 0)
})

// Watch for settings changes (e.g., when loaded from API)
watch(() => settingsStore.settings, (newSettings) => {
  if (newSettings?.model && isInitialized.value) {
    console.log('[MainAgentConfig] Settings updated, re-initializing')
    isUpdating.value = true
    initializeFromStore()
    setTimeout(() => {
      isUpdating.value = false
    }, 100)
  }
}, { deep: true })

// Watch for local changes and sync to store - with debounce and guard
let syncTimeout: ReturnType<typeof setTimeout> | null = null
watch(mainAgentConfig, (newConfig) => {
  // Skip if not initialized or already updating
  if (!isInitialized.value || isUpdating.value || !settingsStore.settings) {
    return
  }

  // Debounce to prevent rapid updates
  if (syncTimeout) {
    clearTimeout(syncTimeout)
  }

  syncTimeout = setTimeout(() => {
    if (isUpdating.value) return
    isUpdating.value = true

    try {
      // Update model config
      if (!settingsStore.settings!.model) {
        settingsStore.settings!.model = {
          provider: '',
          model: '',
          temperature: 0.7,
          max_tokens: 4096,
          max_iterations: 9999
        }
      }

      settingsStore.settings!.model.provider = newConfig.provider
      settingsStore.settings!.model.model = newConfig.model
      settingsStore.settings!.model.temperature = newConfig.temperature
      settingsStore.settings!.model.max_tokens = newConfig.max_tokens
      settingsStore.settings!.model.max_iterations = newConfig.max_iterations

      // Update provider config
      if (!settingsStore.settings!.providers) {
        settingsStore.settings!.providers = {}
      }

      settingsStore.settings!.providers[newConfig.provider] = {
        enabled: true,
        api_key: newConfig.api_key,
        api_base: newConfig.api_base || undefined
      }
    } finally {
      // Reset flag after a tick to allow future updates
      setTimeout(() => {
        isUpdating.value = false
      }, 100)
    }
  }, 300) // 300ms debounce
}, { deep: true })

// Handle test result
const handleTest = (success: boolean) => {
  console.log('Main agent test result:', success)
}
</script>

<style scoped>
.main-agent-config {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.extra-params {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.value {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
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
</style>
