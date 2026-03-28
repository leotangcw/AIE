<template>
  <div class="enhanced-models-config">
    <div class="section-header">
      <h3 class="section-title">
        {{ $t('settings.models.enhanced.title') }}
      </h3>
      <p class="section-desc">
        {{ $t('settings.models.enhanced.description') }}
      </p>
    </div>

    <!-- Model Type Tabs -->
    <div class="model-type-tabs">
      <button
        v-for="type in modelTypes"
        :key="type.value"
        :class="['type-tab', { active: activeType === type.value }]"
        @click="activeType = type.value"
      >
        <component :is="type.icon" :size="18" />
        <span>{{ type.label }}</span>
      </button>
    </div>

    <!-- Model List for Current Type -->
    <div class="models-list-container">
      <!-- Empty State -->
      <div v-if="filteredModels.length === 0" class="empty-state">
        <component :is="getEmptyIcon()" :size="48" />
        <p>{{ $t('settings.models.enhanced.emptyState') }}</p>
        <Button variant="secondary" @click="addModel">
          <PlusIcon :size="16" />
          {{ $t('settings.models.enhanced.addModel') }}
        </Button>
      </div>

      <!-- Models List -->
      <div v-else class="models-list">
        <div
          v-for="model in filteredModels"
          :key="model.id"
          class="model-item"
          @click="editModel(model)"
        >
          <div class="model-info">
            <div class="model-header">
              <span class="model-name">{{ model.model }}</span>
              <span v-if="model.priority > 0" class="model-priority">
                {{ $t('settings.models.enhanced.priority') }}: {{ model.priority }}
              </span>
            </div>
            <div class="model-meta">
              <span class="model-provider">{{ getProviderLabel(model.provider) }}</span>
              <span v-if="model.description" class="model-description">{{ model.description }}</span>
            </div>
            <div v-if="model.capabilities?.length" class="model-capabilities">
              <span
                v-for="cap in model.capabilities.slice(0, 3)"
                :key="cap"
                class="capability-tag"
              >
                {{ cap }}
              </span>
              <span v-if="model.capabilities.length > 3" class="capability-more">
                +{{ model.capabilities.length - 3 }}
              </span>
            </div>
          </div>
          <div class="model-actions" @click.stop>
            <ToggleSwitch v-model="model.enabled" size="sm" @update:model-value="toggleModelEnabled(model)" />
            <Button size="sm" variant="ghost" @click.stop="deleteModel(model)">
              <TrashIcon :size="16" />
            </Button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Model Button -->
    <div v-if="filteredModels.length > 0" class="add-model-section">
      <Button variant="secondary" @click="addModel">
        <PlusIcon :size="16" />
        {{ $t('settings.models.enhanced.addModel') }}
      </Button>
    </div>

    <!-- Model Edit Dialog -->
    <ModelEditDialog
      v-if="editingModel"
      :model="editingModel"
      :model-type="activeType"
      :providers="providers"
      @save="saveModel"
      @close="closeEditDialog"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Plus as PlusIcon,
  Trash2 as TrashIcon,
  Image as ImageIcon,
  Video as VideoIcon,
  Music as MusicIcon,
  Headphones as HeadphonesIcon,
  Box as BoxIcon,
  Settings as SettingsIcon,
  Sparkles as SparklesIcon
} from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import ToggleSwitch from '@/components/ui/ToggleSwitch.vue'
import ModelEditDialog from './ModelEditDialog.vue'
import { useSettingsStore } from '@/store/settings'
import { settingsAPI } from '@/api'
import type { ProviderMetadata } from '@/types/settings'

interface EnhancedModel {
  id: string
  model_type: string
  provider: string
  model: string
  enabled: boolean
  description: string
  capabilities: string[]
  priority: number
  api_key?: string
  api_base?: string
  temperature?: number
  max_tokens?: number
  advanced_params?: Record<string, any>
}

const { t } = useI18n()
const settingsStore = useSettingsStore()

const activeType = ref<string>('multimodal')
const editingModel = ref<EnhancedModel | null>(null)
const providers = ref<ProviderMetadata[]>([])

const modelTypes = computed(() => [
  { value: 'multimodal', label: t('settings.models.enhanced.types.multimodal'), icon: ImageIcon },
  { value: 'image_gen', label: t('settings.models.enhanced.types.imageGen'), icon: SparklesIcon },
  { value: 'video_gen', label: t('settings.models.enhanced.types.videoGen'), icon: VideoIcon },
  { value: 'music_gen', label: t('settings.models.enhanced.types.musicGen'), icon: MusicIcon },
  { value: 'audio_gen', label: t('settings.models.enhanced.types.audioGen'), icon: HeadphonesIcon },
  { value: '3d_gen', label: t('settings.models.enhanced.types.threeD'), icon: BoxIcon },
  { value: 'custom', label: t('settings.models.enhanced.types.custom'), icon: SettingsIcon }
])

const enhancedModels = ref<EnhancedModel[]>([])

const filteredModels = computed(() => {
  return enhancedModels.value.filter(m => m.model_type === activeType.value)
})

const getEmptyIcon = () => {
  const type = modelTypes.value.find(t => t.value === activeType.value)
  return type?.icon || SettingsIcon
}

const getProviderLabel = (providerId: string): string => {
  const provider = providers.value.find(p => p.id === providerId)
  return provider?.name || providerId
}

const addModel = () => {
  const newModel: EnhancedModel = {
    id: `enhanced_${Date.now()}`,
    model_type: activeType.value,
    provider: '',
    model: '',
    enabled: true,
    description: '',
    capabilities: [],
    priority: 0,
    temperature: 0.7,
    max_tokens: 4096,
    advanced_params: {}
  }
  editingModel.value = newModel
}

const editModel = (model: EnhancedModel) => {
  editingModel.value = { ...model }
}

const closeEditDialog = () => {
  editingModel.value = null
}

const saveModel = (model: EnhancedModel) => {
  const existingIndex = enhancedModels.value.findIndex(m => m.id === model.id)
  if (existingIndex >= 0) {
    enhancedModels.value[existingIndex] = model
  } else {
    enhancedModels.value.push(model)
  }
  closeEditDialog()
  syncToStore()
}

const deleteModel = (model: EnhancedModel) => {
  if (confirm(t('settings.models.enhanced.confirmDelete'))) {
    enhancedModels.value = enhancedModels.value.filter(m => m.id !== model.id)
    syncToStore()
  }
}

const toggleModelEnabled = (_model: EnhancedModel) => {
  syncToStore()
}

const syncToStore = () => {
  if (settingsStore.settings) {
    if (!settingsStore.settings.enhanced_models) {
      settingsStore.settings.enhanced_models = []
    }
    settingsStore.settings.enhanced_models = enhancedModels.value.map(m => ({
      id: m.id,
      model_type: m.model_type,
      provider: m.provider,
      model: m.model,
      enabled: m.enabled,
      description: m.description,
      capabilities: m.capabilities,
      priority: m.priority,
      api_key: m.api_key,
      api_base: m.api_base,
      temperature: m.temperature,
      max_tokens: m.max_tokens,
      advanced_params: m.advanced_params
    }))
  }
}

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
  console.log('[EnhancedModelsConfig] initializeFromStore called')
  console.log('[EnhancedModelsConfig] settingsStore.settings:', settingsStore.settings)
  console.log('[EnhancedModelsConfig] enhanced_models:', settingsStore.settings?.enhanced_models)

  if (settingsStore.settings?.enhanced_models) {
    enhancedModels.value = settingsStore.settings.enhanced_models.map(m => ({
      id: m.id,
      model_type: m.model_type,
      provider: m.provider,
      model: m.model,
      enabled: m.enabled ?? true,
      description: m.description ?? '',
      capabilities: m.capabilities ?? [],
      priority: m.priority ?? 0,
      api_key: m.api_key,
      api_base: m.api_base,
      temperature: m.temperature,
      max_tokens: m.max_tokens,
      advanced_params: m.advanced_params
    }))
    console.log('[EnhancedModelsConfig] Loaded models:', enhancedModels.value.length)
  } else {
    console.log('[EnhancedModelsConfig] No enhanced_models in store')
  }
}

// Initialize on mount
onMounted(() => {
  initializeFromStore()
})

// Watch for settings changes from store
watch(() => settingsStore.settings?.enhanced_models, (newModels) => {
  console.log('[EnhancedModelsConfig] Watch triggered, newModels:', newModels)
  if (newModels && newModels.length > 0) {
    enhancedModels.value = newModels.map(m => ({
      id: m.id,
      model_type: m.model_type,
      provider: m.provider,
      model: m.model,
      enabled: m.enabled ?? true,
      description: m.description ?? '',
      capabilities: m.capabilities ?? [],
      priority: m.priority ?? 0,
      api_key: m.api_key,
      api_base: m.api_base,
      temperature: m.temperature,
      max_tokens: m.max_tokens,
      advanced_params: m.advanced_params
    }))
    console.log('[EnhancedModelsConfig] Updated models from watch:', enhancedModels.value.length)
  }
}, { deep: true, immediate: true })
</script>

<style scoped>
.enhanced-models-config {
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

.model-type-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.type-tab {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-base);
}

.type-tab:hover {
  border-color: var(--color-primary);
  color: var(--text-primary);
}

.type-tab.active {
  border-color: var(--color-primary);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.1) 100%);
  color: var(--color-primary);
}

.models-list-container {
  min-height: 200px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-2xl);
  color: var(--text-tertiary);
}

.empty-state p {
  margin: 0;
  font-size: var(--font-size-sm);
}

.models-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.model-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-base);
}

.model-item:hover {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.model-info {
  flex: 1;
  min-width: 0;
}

.model-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.model-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.model-priority {
  font-size: var(--font-size-xs);
  padding: 2px 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
}

.model-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xs);
}

.model-provider {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
}

.model-description {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-capabilities {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-xs);
}

.capability-tag {
  font-size: var(--font-size-xs);
  padding: 2px 6px;
  background: rgba(59, 130, 246, 0.1);
  color: var(--color-primary);
  border-radius: var(--radius-sm);
}

.capability-more {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}

.model-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-shrink: 0;
}

.add-model-section {
  display: flex;
  justify-content: flex-start;
}
</style>
