<template>
  <div class="sub-agent-config">
    <ModelConfigCard
      :title="$t('settings.models.subAgent.title')"
      :description="$t('settings.models.subAgent.description')"
      v-model:config="subAgentConfig"
      :providers="providers"
      :show-enable="true"
      :show-advanced="true"
      :show-test-button="true"
      :needs-api-config="true"
      :max-tokens-limit="8192"
      :model-placeholder="$t('settings.models.subAgent.modelPlaceholder')"
      @test="handleTest"
    >
      <template #extra>
        <!-- Sub Agent specific parameters -->
        <div class="extra-params">
          <div class="form-group">
            <label class="label">
              {{ $t('settings.models.maxConcurrent') }}
              <span class="value">{{ subAgentConfig.max_concurrent }}</span>
            </label>
            <p class="help-text">{{ $t('settings.models.maxConcurrentDesc') }}</p>
            <input
              v-model.number="subAgentConfig.max_concurrent"
              type="range"
              min="1"
              max="10"
              step="1"
              class="slider"
            >
            <div class="slider-labels">
              <span>1</span>
              <span>5</span>
              <span>10</span>
            </div>
          </div>
        </div>
      </template>
    </ModelConfigCard>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, shallowRef } from 'vue'
import ModelConfigCard, { type BaseModelConfig } from './components/ModelConfigCard.vue'
import { useSettingsStore } from '@/store/settings'
import { settingsAPI } from '@/api'
import type { ProviderMetadata } from '@/types/settings'

interface SubAgentConfigData extends BaseModelConfig {
  max_concurrent: number
}

const settingsStore = useSettingsStore()

// Use shallowRef to prevent deep reactivity on the config object
const isUpdating = shallowRef(false)
const isInitialized = shallowRef(false)

// Load all providers from API (same as MainAgentConfig)
const providers = ref<ProviderMetadata[]>([])

const subAgentConfig = ref<SubAgentConfigData>({
  enabled: false,
  provider: 'qwen',
  model: 'qwen-turbo',
  api_key: '',
  api_base: '',
  temperature: 0.5,
  max_tokens: 2048,
  max_concurrent: 3,
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
  if (!settingsStore.settings?.sub_agent) {
    console.log('[SubAgentConfig] No sub_agent config in store yet')
    return false
  }

  const config = settingsStore.settings.sub_agent
  const providerConfig = settingsStore.settings.providers?.[config.provider || 'qwen']

  console.log('[SubAgentConfig] providerId:', config.provider)
  console.log('[SubAgentConfig] providerConfig:', providerConfig)

  subAgentConfig.value = {
    enabled: config.enabled ?? false,
    provider: config.provider ?? 'qwen',
    model: config.model ?? 'qwen-turbo',
    api_key: providerConfig?.api_key || '',
    api_base: providerConfig?.api_base || '',
    temperature: config.temperature ?? 0.5,
    max_tokens: config.max_tokens ?? 2048,
    max_concurrent: config.max_concurrent ?? 3,
    advanced_params: {}
  }

  console.log('[SubAgentConfig] Initialized config:', subAgentConfig.value)
  return true
}

// Initialize on mount
onMounted(() => {
  console.log('[SubAgentConfig] Mounting, settings:', settingsStore.settings)
  initializeFromStore()

  // Mark as initialized after a tick to prevent immediate watch trigger
  setTimeout(() => {
    isInitialized.value = true
  }, 0)
})

// Watch for settings changes (e.g., when loaded from API)
watch(() => settingsStore.settings, (newSettings) => {
  if (newSettings?.sub_agent && isInitialized.value) {
    console.log('[SubAgentConfig] Settings updated, re-initializing')
    isUpdating.value = true
    initializeFromStore()
    setTimeout(() => {
      isUpdating.value = false
    }, 100)
  }
}, { deep: true })

// Watch for local changes and sync to store - with debounce and guard
let syncTimeout: ReturnType<typeof setTimeout> | null = null
watch(subAgentConfig, (newConfig) => {
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
      if (!settingsStore.settings!.sub_agent) {
        settingsStore.settings!.sub_agent = {
          enabled: false,
          provider: 'qwen',
          model: 'qwen-turbo',
          max_concurrent: 3,
          temperature: 0.5,
          max_tokens: 2048
        }
      }

      const target = settingsStore.settings!.sub_agent
      target.enabled = newConfig.enabled ?? false
      target.provider = newConfig.provider
      target.model = newConfig.model
      target.temperature = newConfig.temperature
      target.max_tokens = newConfig.max_tokens
      target.max_concurrent = newConfig.max_concurrent

      // Update provider config if API key/base is provided
      if (newConfig.api_key || newConfig.api_base) {
        if (!settingsStore.settings!.providers) {
          settingsStore.settings!.providers = {}
        }
        settingsStore.settings!.providers[newConfig.provider] = {
          enabled: true,
          api_key: newConfig.api_key,
          api_base: newConfig.api_base || undefined
        }
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
  console.log('Sub agent test result:', success)
}
</script>

<style scoped>
.sub-agent-config {
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
