<template>
  <div class="knowledge-hub-config">
    <div class="section-header">
      <h3>{{ $t('knowledgeHub.title') }}</h3>
      <p>{{ $t('knowledgeHub.description') }}</p>
    </div>

    <!-- 处理模式 -->
    <div class="config-section">
      <h4>{{ $t('knowledgeHub.processingMode') }}</h4>
      <div class="mode-selector">
        <label v-for="mode in modes" :key="mode.value" class="mode-option">
          <input
            type="radio"
            v-model="config.default_mode"
            :value="mode.value"
            @change="updateConfig"
          />
          <span class="mode-label">{{ $t(mode.labelKey) }}</span>
        </label>
      </div>
    </div>

    <!-- LLM配置 -->
    <div class="config-section" v-if="config.default_mode !== 'direct'">
      <h4>{{ $t('knowledgeHub.llmConfig') }}</h4>

      <div class="form-group">
        <label class="toggle-label">
          <span>{{ $t('knowledgeHub.enableLLM') }}</span>
          <label class="toggle-switch">
            <input type="checkbox" v-model="config.llm.enabled" @change="updateConfig" />
            <span class="toggle-slider"></span>
          </label>
        </label>
      </div>

      <div v-if="config.llm.enabled" class="llm-options">
        <div class="form-group">
          <label>{{ $t('knowledgeHub.promptStyle') }}</label>
          <select v-model="config.llm.prompt_style" @change="updateConfig">
            <option value="compress">{{ $t('knowledgeHub.styleCompress') }}</option>
            <option value="restate">{{ $t('knowledgeHub.styleRestate') }}</option>
            <option value="rework">{{ $t('knowledgeHub.styleRework') }}</option>
          </select>
        </div>

        <div class="form-group">
          <label>{{ $t('knowledgeHub.model') }}</label>
          <input v-model="config.llm.model" type="text" @change="updateConfig" />
        </div>

        <div class="form-group">
          <label>{{ $t('knowledgeHub.temperature') }}: {{ config.llm.temperature }}</label>
          <input
            type="range"
            v-model.number="config.llm.temperature"
            min="0"
            max="1"
            step="0.1"
            @change="updateConfig"
          />
        </div>

        <div class="form-group">
          <label>{{ $t('knowledgeHub.maxTokens') }}</label>
          <input v-model.number="config.llm.max_tokens" type="number" @change="updateConfig" />
        </div>
      </div>
    </div>

    <!-- 缓存配置 -->
    <div class="config-section">
      <h4>{{ $t('knowledgeHub.cache') }}</h4>
      <div class="form-group">
        <label class="toggle-label">
          <span>{{ $t('knowledgeHub.enableCache') }}</span>
          <label class="toggle-switch">
            <input type="checkbox" v-model="config.cache.enabled" @change="updateConfig" />
            <span class="toggle-slider"></span>
          </label>
        </label>
      </div>
      <div class="form-group">
        <label>{{ $t('knowledgeHub.cacheTTL') }} (秒)</label>
        <input v-model.number="config.cache.ttl" type="number" @change="updateConfig" />
      </div>
      <button class="btn secondary" @click="refreshCache">
        {{ $t('knowledgeHub.refreshCache') }}
      </button>
    </div>

    <!-- 测试检索 -->
    <div class="config-section">
      <h4>{{ $t('knowledgeHub.testRetrieve') }}</h4>
      <div class="test-form">
        <input v-model="testQuery" type="text" :placeholder="$t('knowledgeHub.queryPlaceholder')" />
        <button class="btn primary" @click="testRetrieve" :disabled="testing">
          {{ testing ? $t('knowledgeHub.searching') : $t('knowledgeHub.search') }}
        </button>
      </div>
      <div v-if="testResult" class="test-result">
        <pre>{{ testResult }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import knowledgeHubApi, { type KnowledgeHubConfig } from '@/api/knowledgeHub'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const toast = useToast()

const config = ref<KnowledgeHubConfig>({
  enabled: true,
  default_mode: 'direct',
  llm: {
    enabled: false,
    model: 'gpt-3.5-turbo',
    api_key: '',
    base_url: '',
    temperature: 0.7,
    max_tokens: 2000,
    prompt_style: 'compress'
  },
  cache: {
    enabled: true,
    ttl: 3600,
    max_memory_items: 100
  },
  sources: [],
  storage_dir: 'memory/knowledge_hub'
})

const modes = [
  { value: 'direct', labelKey: 'knowledgeHub.directMode' },
  { value: 'llm', labelKey: 'knowledgeHub.llmMode' },
  { value: 'hybrid', labelKey: 'knowledgeHub.hybridMode' },
  { value: 'graph', labelKey: 'knowledgeHub.graphMode' }
]

const testQuery = ref('')
const testing = ref(false)
const testResult = ref('')

const loadConfig = async () => {
  try {
    const result = await knowledgeHubApi.getConfig()
    config.value = result
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

const updateConfig = async () => {
  try {
    await knowledgeHubApi.updateConfig(config.value)
  } catch (error) {
    console.error('Failed to update config:', error)
  }
}

const refreshCache = async () => {
  try {
    await knowledgeHubApi.refreshCache()
    toast.success(t('knowledgeHub.cacheRefreshed'))
  } catch (error) {
    console.error('Failed to refresh cache:', error)
  }
}

const testRetrieve = async () => {
  if (!testQuery.value.trim()) return

  testing.value = true
  testResult.value = ''

  try {
    const result = await knowledgeHubApi.retrieve({
      query: testQuery.value,
      mode: config.value.default_mode,
      top_k: 5
    })
    testResult.value = JSON.stringify(result, null, 2)
  } catch (error) {
    console.error('Failed to retrieve:', error)
    testResult.value = 'Error: ' + error
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.knowledge-hub-config {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 16px;
}

.config-section {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: 8px;
  padding: 16px;
}

.config-section h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
}

.mode-selector {
  display: flex;
  gap: 16px;
}

.mode-option {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
}

.form-group input[type="text"],
.form-group input[type="number"],
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border-primary);
  border-radius: 6px;
}

.toggle-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: var(--color-border-secondary);
  border-radius: 24px;
  transition: 0.3s;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}

.toggle-switch input:checked + .toggle-slider {
  background-color: var(--color-success);
}

.toggle-switch input:checked + .toggle-slider:before {
  transform: translateX(20px);
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn.primary {
  background: var(--color-primary);
  color: white;
  border: none;
}

.btn.secondary {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
}

.test-form {
  display: flex;
  gap: 8px;
}

.test-form input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--color-border-primary);
  border-radius: 6px;
}

.test-result {
  margin-top: 16px;
  padding: 12px;
  background: var(--color-bg-secondary);
  border-radius: 6px;
  max-height: 300px;
  overflow: auto;
}

.test-result pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
}
</style>
