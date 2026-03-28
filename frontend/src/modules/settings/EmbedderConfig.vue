<template>
  <div class="embedder-config">
    <div class="section-header">
      <h3 class="section-title">
        {{ $t('settings.models.embedder.title') }}
      </h3>
      <p class="section-desc">
        {{ $t('settings.models.embedder.description') }}
      </p>
    </div>

    <!-- Mode Selection -->
    <div class="form-group">
      <label class="label">{{ $t('settings.models.embedder.mode') }}</label>
      <div class="mode-selector">
        <button
          class="mode-btn"
          :class="{ active: useLocal }"
          @click="useLocal = true"
        >
          <CpuIcon :size="18" />
          <span>{{ $t('settings.models.embedder.localMode') }}</span>
        </button>
        <button
          class="mode-btn"
          :class="{ active: !useLocal }"
          @click="useLocal = false"
        >
          <CloudIcon :size="18" />
          <span>{{ $t('settings.models.embedder.apiMode') }}</span>
        </button>
      </div>
      <p class="hint">
        {{ useLocal ? $t('settings.models.embedder.localModeHint') : $t('settings.models.embedder.apiModeHint') }}
      </p>
    </div>

    <!-- Local Model Settings -->
    <div v-if="useLocal" class="settings-form">
      <div class="form-group">
        <label class="label">{{ $t('settings.models.embedder.model') }}</label>
        <Input
          v-model="localConfig.model"
          type="text"
          :placeholder="$t('settings.models.embedder.modelPlaceholder')"
          :disabled="true"
        />
        <p class="hint">{{ $t('settings.models.embedder.modelHint') }}</p>
      </div>

      <div class="form-group">
        <label class="label">
          {{ $t('settings.models.embedder.dimension') }}
          <span class="value">{{ localConfig.dimension }}</span>
        </label>
        <p class="hint">{{ $t('settings.models.embedder.dimensionHint') }}</p>
      </div>

      <div class="form-group">
        <label class="label">{{ $t('settings.models.embedder.device') }}</label>
        <Select
          v-model="localConfig.device"
          :options="deviceOptions"
        />
        <p class="hint">{{ $t('settings.models.embedder.deviceHint') }}</p>
      </div>

      <div class="form-group">
        <label class="checkbox-label">
          <input
            v-model="localConfig.useFp16"
            type="checkbox"
            class="checkbox"
          >
          <span>{{ $t('settings.models.embedder.useFp16') }}</span>
        </label>
        <p class="hint">{{ $t('settings.models.embedder.useFp16Hint') }}</p>
      </div>

      <div class="form-group">
        <label class="checkbox-label">
          <input
            v-model="localConfig.useModelscope"
            type="checkbox"
            class="checkbox"
          >
          <span>{{ $t('settings.models.embedder.useModelscope') }}</span>
        </label>
        <p class="hint">{{ $t('settings.models.embedder.useModelscopeHint') }}</p>
      </div>

      <div class="form-group">
        <label class="label">{{ $t('settings.models.embedder.cacheDir') }}</label>
        <div class="input-with-button">
          <Input
            v-model="localConfig.cacheDir"
            type="text"
            :placeholder="$t('settings.models.embedder.cacheDirPlaceholder')"
          />
          <Button variant="secondary" size="sm" @click="selectCacheDir">
            <FolderOpenIcon :size="16" />
          </Button>
        </div>
        <p class="hint">{{ $t('settings.models.embedder.cacheDirHint') }}</p>
      </div>

      <!-- Model Status -->
      <div class="model-status">
        <div class="status-header">
          <component
            :is="modelStatus.loading ? LoaderIcon : (modelStatus.loaded ? CheckCircleIcon : AlertCircleIcon)"
            :size="18"
            :class="['status-icon', { loading: modelStatus.loading, success: modelStatus.loaded, warning: !modelStatus.loaded }]"
          />
          <span class="status-label">{{ $t('settings.models.embedder.modelStatus') }}</span>
        </div>
        <div class="status-info">
          <span>{{ modelStatus.message }}</span>
        </div>
      </div>
    </div>

    <!-- API Mode Settings using ModelConfigCard pattern -->
    <div v-else class="api-settings">
      <div class="api-config-card">
        <div class="card-header">
          <h4 class="card-title">{{ $t('settings.models.embedder.apiConfig') }}</h4>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label class="label">{{ $t('settings.models.provider') }}</label>
            <Select
              v-model="apiConfig.provider"
              :options="apiProviderOptions"
            />
            <p class="hint">{{ $t('settings.models.embedder.apiProviderHint') }}</p>
          </div>

          <div class="form-group">
            <label class="label">{{ $t('settings.models.model') }}</label>
            <Input
              v-model="apiConfig.model"
              type="text"
              :placeholder="currentApiModelPlaceholder"
            />
            <p class="hint">{{ $t('settings.models.embedder.apiModelHint') }}</p>
          </div>
        </div>

        <div class="form-group">
          <label class="label">
            {{ $t('settings.models.embedder.apiDimension') }}
            <span class="value">{{ getApiDimension() }}</span>
          </label>
          <p class="hint">{{ $t('settings.models.embedder.apiDimensionHint') }}</p>
        </div>

        <div class="form-group">
          <label class="label">{{ $t('settings.models.apiBase') }}</label>
          <Input
            v-model="apiConfig.apiBase"
            type="text"
            :placeholder="$t('settings.models.embedder.apiBasePlaceholder')"
          />
          <p class="hint">{{ $t('settings.models.embedder.apiBaseHint') }}</p>
        </div>

        <!-- Test Connection -->
        <div class="form-group">
          <Button
            variant="secondary"
            :loading="testingApi"
            @click="testApiConnection"
          >
            {{ testingApi ? $t('common.testing') : $t('settings.models.testConnection') }}
          </Button>
        </div>

        <div v-if="apiTestResult" class="test-result" :class="apiTestResult.success ? 'success' : 'error'">
          <component
            :is="apiTestResult.success ? CheckCircleIcon : XCircleIcon"
            :size="16"
          />
          <span>{{ apiTestResult.message }}</span>
        </div>
      </div>
    </div>

    <!-- Dimension Compatibility Warning -->
    <div v-if="showDimensionWarning" class="warning-box">
      <AlertTriangleIcon :size="18" />
      <div class="warning-content">
        <strong>{{ $t('settings.models.embedder.dimensionWarning.title') }}</strong>
        <p>{{ $t('settings.models.embedder.dimensionWarning.message') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Cpu as CpuIcon,
  Cloud as CloudIcon,
  FolderOpen as FolderOpenIcon,
  CheckCircle as CheckCircleIcon,
  XCircle as XCircleIcon,
  AlertCircle as AlertCircleIcon,
  AlertTriangle as AlertTriangleIcon,
  Loader2 as LoaderIcon
} from 'lucide-vue-next'
import Input from '@/components/ui/Input.vue'
import Select from '@/components/ui/Select.vue'
import Button from '@/components/ui/Button.vue'
import { useSettingsStore } from '@/store/settings'
import { settingsAPI } from '@/api'

const { t } = useI18n()
const settingsStore = useSettingsStore()

const useLocal = ref(true)
const isUpdating = ref(false)

const localConfig = reactive({
  model: 'BAAI/bge-m3',
  dimension: 1024,
  device: 'auto',
  useFp16: true,
  useModelscope: true,
  cacheDir: ''
})

const apiConfig = reactive({
  provider: 'qwen_bailian',
  model: 'text-embedding-v3',
  apiBase: ''
})

const modelStatus = reactive({
  loading: false,
  loaded: false,
  message: ''
})

const testingApi = ref(false)
const apiTestResult = ref<{ success: boolean; message: string } | null>(null)

const deviceOptions = computed(() => [
  { value: 'auto', label: t('settings.models.embedder.devices.auto') },
  { value: 'cuda', label: t('settings.models.embedder.devices.cuda') },
  { value: 'cpu', label: t('settings.models.embedder.devices.cpu') }
])

const apiProviderOptions = computed(() => [
  { value: 'qwen_bailian', label: t('settings.models.embedder.apiProviders.qwenBailian') },
  { value: 'openai', label: t('settings.models.embedder.apiProviders.openai') },
  { value: 'zhipu', label: t('settings.models.embedder.apiProviders.zhipu') },
  { value: 'jina', label: t('settings.models.embedder.apiProviders.jina') }
])

const apiDimensions: Record<string, number> = {
  'qwen_bailian': 1024,
  'openai': 1536,
  'zhipu': 1024,
  'jina': 1024
}

const apiModelDefaults: Record<string, string> = {
  'qwen_bailian': 'text-embedding-v3',
  'openai': 'text-embedding-3-small',
  'zhipu': 'embedding-3',
  'jina': 'jina-embeddings-v2-base-zh'
}

const currentApiModelPlaceholder = computed(() => {
  return apiModelDefaults[apiConfig.provider] || 'embedding-model'
})

const showDimensionWarning = computed(() => {
  if (useLocal.value) return false
  const apiDim = getApiDimension()
  return apiDim !== 1024 // BGE-M3 uses 1024
})

const getApiDimension = () => {
  return apiDimensions[apiConfig.provider] || 1024
}

const selectCacheDir = async () => {
  // In a desktop app, this would open a folder picker
  console.log('Select cache directory')
}

const testApiConnection = async () => {
  testingApi.value = true
  apiTestResult.value = null

  try {
    const response = await settingsAPI.testEmbedder({
      provider: apiConfig.provider,
      model: apiConfig.model,
      api_base: apiConfig.apiBase
    })

    apiTestResult.value = {
      success: response.success,
      message: response.success
        ? t('settings.models.embedder.testSuccess')
        : (response.error || t('settings.models.embedder.testFailed'))
    }
  } catch (error: any) {
    apiTestResult.value = {
      success: false,
      message: error.response?.data?.error || error.message || t('settings.models.embedder.testFailed')
    }
  } finally {
    testingApi.value = false
  }
}

const checkModelStatus = async () => {
  modelStatus.loading = true
  modelStatus.message = t('settings.models.embedder.checkingModel')

  try {
    const response = await settingsAPI.getEmbedderStatus()
    modelStatus.loaded = response.loaded
    modelStatus.message = response.loaded
      ? t('settings.models.embedder.modelLoaded', { path: response.cache_path })
      : t('settings.models.embedder.modelNotLoaded')
  } catch (error) {
    modelStatus.loaded = false
    modelStatus.message = t('settings.models.embedder.modelCheckFailed')
  } finally {
    modelStatus.loading = false
  }
}

// Initialize from store
onMounted(() => {
  if (settingsStore.settings?.built_in?.embedding) {
    isUpdating.value = true
    const config = settingsStore.settings.built_in.embedding
    const hasApiFallback = config.api_fallback && config.api_fallback.provider

    useLocal.value = !hasApiFallback
    localConfig.model = config.model ?? 'BAAI/bge-m3'
    localConfig.dimension = config.dimension ?? 1024
    localConfig.device = config.device ?? 'auto'
    localConfig.useFp16 = config.use_fp16 ?? true
    localConfig.useModelscope = config.use_modelscope ?? true
    localConfig.cacheDir = config.cache_dir ?? ''

    if (config.api_fallback) {
      apiConfig.provider = config.api_fallback.provider ?? 'qwen_bailian'
      apiConfig.model = config.api_fallback.model ?? 'text-embedding-v3'
      apiConfig.apiBase = config.api_fallback.api_base ?? ''
    }

    isUpdating.value = false
  }

  if (useLocal.value) {
    checkModelStatus()
  }
})

// Watch for settings changes from store
watch(() => settingsStore.settings?.built_in?.embedding, (newConfig) => {
  if (newConfig && !isUpdating.value) {
    isUpdating.value = true
    const hasApiFallback = newConfig.api_fallback && newConfig.api_fallback.provider

    useLocal.value = !hasApiFallback
    localConfig.model = newConfig.model ?? 'BAAI/bge-m3'
    localConfig.dimension = newConfig.dimension ?? 1024
    localConfig.device = newConfig.device ?? 'auto'
    localConfig.useFp16 = newConfig.use_fp16 ?? true
    localConfig.useModelscope = newConfig.use_modelscope ?? true
    localConfig.cacheDir = newConfig.cache_dir ?? ''

    if (newConfig.api_fallback) {
      apiConfig.provider = newConfig.api_fallback.provider ?? 'qwen_bailian'
      apiConfig.model = newConfig.api_fallback.model ?? 'text-embedding-v3'
      apiConfig.apiBase = newConfig.api_fallback.api_base ?? ''
    }
    isUpdating.value = false
  }
}, { deep: true })

// Watch for local changes and sync to store
watch([useLocal, localConfig, apiConfig], () => {
  if (!isUpdating.value && settingsStore.settings) {
    isUpdating.value = true
    if (!settingsStore.settings.built_in) {
      settingsStore.settings.built_in = { embedding: {} }
    }
    if (!settingsStore.settings.built_in.embedding) {
      settingsStore.settings.built_in.embedding = {}
    }

    const embedding = settingsStore.settings.built_in.embedding
    embedding.model = localConfig.model
    embedding.dimension = localConfig.dimension
    embedding.device = localConfig.device
    embedding.use_fp16 = localConfig.useFp16
    embedding.use_modelscope = localConfig.useModelscope
    embedding.cache_dir = localConfig.cacheDir || null

    // Set API fallback based on mode
    if (!useLocal.value) {
      embedding.api_fallback = {
        provider: apiConfig.provider,
        model: apiConfig.model,
        api_base: apiConfig.apiBase || null
      }
    } else {
      embedding.api_fallback = null
    }

    isUpdating.value = false
  }
}, { deep: true })

// Check model status when switching to local mode
watch(useLocal, (isLocal) => {
  if (isLocal) {
    checkModelStatus()
  }
})

// Update model when provider changes
watch(() => apiConfig.provider, (newProvider) => {
  apiConfig.model = apiModelDefaults[newProvider] || ''
})
</script>

<style scoped>
.embedder-config {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.section-header {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.section-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
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

.mode-selector {
  display: flex;
  gap: var(--spacing-sm);
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-base);
}

.mode-btn:hover {
  border-color: var(--color-primary);
  color: var(--text-primary);
}

.mode-btn.active {
  border-color: var(--color-primary);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.1) 100%);
  color: var(--color-primary);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  cursor: pointer;
}

.checkbox {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-base);
}

.checkbox:checked {
  background-color: var(--color-primary);
  border-color: var(--color-primary);
}

.hint {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin: 0;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.api-settings {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.api-config-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.card-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.input-with-button {
  display: flex;
  gap: var(--spacing-sm);
}

.input-with-button > *:first-child {
  flex: 1;
}

.model-status {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.status-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.status-icon {
  flex-shrink: 0;
}

.status-icon.loading {
  color: var(--color-primary);
  animation: spin 1s linear infinite;
}

.status-icon.success {
  color: var(--color-success);
}

.status-icon.warning {
  color: var(--color-warning);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.status-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.status-info {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  padding-left: calc(18px + var(--spacing-sm));
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

.warning-box {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: var(--radius-md);
  color: var(--color-warning);
}

.warning-box strong {
  display: block;
  font-size: var(--font-size-sm);
  margin-bottom: var(--spacing-xs);
}

.warning-box p {
  font-size: var(--font-size-xs);
  margin: 0;
  opacity: 0.9;
}

.warning-content {
  flex: 1;
}
</style>
