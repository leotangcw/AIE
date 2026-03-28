<template>
  <div class="dialog-overlay" @click.self="$emit('close')">
    <div class="dialog-container">
      <div class="dialog-header">
        <h3 class="dialog-title">
          {{ isNew ? $t('settings.models.enhanced.addModel') : $t('settings.models.enhanced.editModel') }}
        </h3>
        <button class="close-btn" @click="$emit('close')">
          <XIcon :size="20" />
        </button>
      </div>

      <div class="dialog-content">
        <!-- Model Type Selection -->
        <div class="form-group">
          <label class="label">{{ $t('settings.models.enhanced.modelType') }}</label>
          <Select
            v-model="localModel.model_type"
            :options="modelTypeOptions"
          />
        </div>

        <!-- Provider and Model -->
        <div class="form-row">
          <div class="form-group">
            <label class="label">{{ $t('settings.models.provider') }}</label>
            <Select
              v-model="localModel.provider"
              :options="providerOptions"
            />
          </div>
          <div class="form-group">
            <label class="label">{{ $t('settings.models.model') }}</label>
            <Input
              v-model="localModel.model"
              type="text"
              :placeholder="$t('settings.models.enhanced.modelPlaceholder')"
            />
          </div>
        </div>

        <!-- API Configuration -->
        <div class="form-section">
          <div class="section-title" @click="showApiConfig = !showApiConfig">
            <span>{{ $t('settings.models.apiConfig') }}</span>
            <ChevronIcon :class="['chevron-icon', { expanded: showApiConfig }]" />
          </div>
          <div v-if="showApiConfig" class="section-content">
            <div class="form-group">
              <label class="label">
                {{ $t('settings.models.apiKey') }}
                <span v-if="isLocalProvider" class="label-hint">({{ $t('common.optional') }})</span>
              </label>
              <Input
                v-model="localModel.api_key"
                type="password"
                :placeholder="$t('settings.models.apiKeyPlaceholder')"
              />
            </div>
            <div class="form-group">
              <label class="label">{{ $t('settings.models.apiBase') }}</label>
              <Input
                v-model="localModel.api_base"
                type="text"
                :placeholder="$t('settings.models.apiBasePlaceholder')"
              />
            </div>
          </div>
        </div>

        <!-- Basic Parameters -->
        <div class="form-section">
          <div class="section-title" @click="showBasicParams = !showBasicParams">
            <span>{{ $t('settings.models.basicParams') }}</span>
            <ChevronIcon :class="['chevron-icon', { expanded: showBasicParams }]" />
          </div>
          <div v-if="showBasicParams" class="section-content">
            <div class="form-group">
              <label class="label">
                {{ $t('settings.models.temperature') }}
                <span class="value">{{ localModel.temperature }}</span>
              </label>
              <input
                v-model.number="localModel.temperature"
                type="range"
                min="0"
                max="2"
                step="0.1"
                class="slider"
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
                <span class="value">{{ localModel.max_tokens }}</span>
              </label>
              <input
                v-model.number="localModel.max_tokens"
                type="range"
                min="256"
                max="32768"
                step="256"
                class="slider"
              >
              <div class="slider-labels">
                <span>256</span>
                <span>16K</span>
                <span>32K</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Advanced Parameters (JSON Editor) -->
        <div class="form-section">
          <div class="section-title" @click="showAdvanced = !showAdvanced">
            <span>{{ $t('settings.models.advancedParams') }}</span>
            <ChevronIcon :class="['chevron-icon', { expanded: showAdvanced }]" />
          </div>
          <div v-if="showAdvanced" class="section-content">
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
              <Button size="sm" variant="secondary" @click="applyTemplate('image')">
                {{ $t('settings.models.templates.image') }}
              </Button>
              <Button size="sm" variant="secondary" @click="applyTemplate('video')">
                {{ $t('settings.models.templates.video') }}
              </Button>
            </div>
            <p v-if="jsonError" class="error-message">{{ jsonError }}</p>
          </div>
        </div>

        <!-- Description -->
        <div class="form-group">
          <label class="label">{{ $t('settings.models.enhanced.description') }}</label>
          <Input
            v-model="localModel.description"
            type="text"
            :placeholder="$t('settings.models.enhanced.descriptionPlaceholder')"
          />
        </div>

        <!-- Priority -->
        <div class="form-group">
          <label class="label">
            {{ $t('settings.models.enhanced.priority') }}
            <span class="value">{{ localModel.priority }}</span>
          </label>
          <input
            v-model.number="localModel.priority"
            type="range"
            min="0"
            max="100"
            step="1"
            class="slider"
          >
          <div class="slider-labels">
            <span>0</span>
            <span>50</span>
            <span>100</span>
          </div>
        </div>

        <!-- Capabilities -->
        <div class="form-group">
          <label class="label">{{ $t('settings.models.enhanced.capabilities') }}</label>
          <div class="capability-tags">
            <span
              v-for="cap in availableCapabilities"
              :key="cap"
              :class="['capability-tag', { active: localModel.capabilities.includes(cap) }]"
              @click="toggleCapability(cap)"
            >
              {{ cap }}
            </span>
          </div>
        </div>
      </div>

      <div class="dialog-footer">
        <Button variant="secondary" @click="$emit('close')">
          {{ $t('common.cancel') }}
        </Button>
        <Button variant="primary" @click="handleSave">
          {{ $t('common.save') }}
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  X as XIcon,
  ChevronDown as ChevronIcon
} from 'lucide-vue-next'
import Input from '@/components/ui/Input.vue'
import Select from '@/components/ui/Select.vue'
import Button from '@/components/ui/Button.vue'
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

interface Props {
  model: EnhancedModel
  modelType: string
  providers: ProviderMetadata[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  save: [model: EnhancedModel]
  close: []
}>()

const { t } = useI18n()

const isNew = computed(() => !props.model.provider || !props.model.model)

// UI state
const showApiConfig = ref(true)
const showBasicParams = ref(true)
const showAdvanced = ref(false)

// Form state
const localModel = ref<EnhancedModel>({
  id: '',
  model_type: '',
  provider: '',
  model: '',
  enabled: true,
  description: '',
  capabilities: [],
  priority: 0,
  api_key: '',
  api_base: '',
  temperature: 0.7,
  max_tokens: 4096,
  advanced_params: {}
})

const advancedJson = ref('{}')
const jsonError = ref('')

// Model type options
const modelTypeOptions = computed(() => [
  { value: 'multimodal', label: t('settings.models.enhanced.types.multimodal') },
  { value: 'image_gen', label: t('settings.models.enhanced.types.imageGen') },
  { value: 'video_gen', label: t('settings.models.enhanced.types.videoGen') },
  { value: 'music_gen', label: t('settings.models.enhanced.types.musicGen') },
  { value: 'audio_gen', label: t('settings.models.enhanced.types.audioGen') },
  { value: '3d_gen', label: t('settings.models.enhanced.types.threeD') },
  { value: 'custom', label: t('settings.models.enhanced.types.custom') }
])

// Provider options
const providerOptions = computed(() =>
  props.providers.map(p => ({
    value: p.id,
    label: t(`settings.providers.${p.id}`, p.name)
  }))
)

// Local provider check
const LOCAL_PROVIDERS = ['ollama', 'vllm', 'lm_studio']
const isLocalProvider = computed(() => LOCAL_PROVIDERS.includes(localModel.value.provider))

// Available capabilities based on model type
const availableCapabilities = computed(() => {
  const capabilitiesByType: Record<string, string[]> = {
    'multimodal': ['image_understanding', 'audio_understanding', 'video_understanding'],
    'image_gen': ['text_to_image', 'image_to_image', 'inpainting', 'upscaling'],
    'video_gen': ['text_to_video', 'image_to_video', 'video_editing'],
    'music_gen': ['music_generation', 'lyrics_generation'],
    'audio_gen': ['text_to_speech', 'speech_to_text', 'voice_cloning'],
    '3d_gen': ['text_to_3d', 'image_to_3d', '3d_editing'],
    'custom': ['custom']
  }
  return capabilitiesByType[localModel.value.model_type] || []
})

// Initialize from props
onMounted(() => {
  localModel.value = { ...props.model }
  if (!localModel.value.id) {
    localModel.value.id = `enhanced_${Date.now()}`
  }
  if (localModel.value.advanced_params) {
    advancedJson.value = JSON.stringify(localModel.value.advanced_params, null, 2)
  }
})

// Watch JSON editor changes
watch(advancedJson, (newJson) => {
  try {
    if (newJson.trim()) {
      const parsed = JSON.parse(newJson)
      localModel.value.advanced_params = parsed
      jsonError.value = ''
    }
  } catch (e) {
    jsonError.value = t('settings.models.invalidJson')
  }
})

// Apply template for advanced params
const applyTemplate = (template: string) => {
  const templates: Record<string, Record<string, any>> = {
    default: {
      top_p: 0.9,
      frequency_penalty: 0.0,
      presence_penalty: 0.0
    },
    image: {
      size: '1024x1024',
      quality: 'standard',
      n: 1
    },
    video: {
      duration: 5,
      fps: 24,
      resolution: '720p'
    }
  }

  const selected = templates[template] || templates.default
  advancedJson.value = JSON.stringify(selected, null, 2)
}

// Toggle capability
const toggleCapability = (cap: string) => {
  const index = localModel.value.capabilities.indexOf(cap)
  if (index >= 0) {
    localModel.value.capabilities.splice(index, 1)
  } else {
    localModel.value.capabilities.push(cap)
  }
}

// Save handler
const handleSave = () => {
  emit('save', { ...localModel.value })
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog-container {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.dialog-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-base);
}

.close-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.dialog-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  border-top: 1px solid var(--border-color);
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

@media (max-width: 480px) {
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

.label-hint {
  font-weight: var(--font-weight-normal);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.value {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.form-section {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.section-title:hover {
  background: var(--bg-hover);
}

.section-content {
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.chevron-icon {
  transition: transform var(--transition-base);
}

.chevron-icon.expanded {
  transform: rotate(180deg);
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
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  transition: all var(--transition-base);
}

.slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-primary);
  cursor: pointer;
  border: none;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
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

.capability-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.capability-tag {
  padding: var(--spacing-xs) var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-base);
}

.capability-tag:hover {
  border-color: var(--color-primary);
  color: var(--text-primary);
}

.capability-tag.active {
  border-color: var(--color-primary);
  background: rgba(59, 130, 246, 0.1);
  color: var(--color-primary);
}
</style>
