<template>
  <div class="knowledge-search-system">
    <!-- 企业规章制度 -->
    <div class="regulations-card" @click="scrollToRegulationSource">
      <div class="regulations-icon">
        <ShieldCheck :size="28" />
      </div>
      <div class="regulations-info">
        <h4>{{ $t('knowledgeSearch.regulations.title') }}</h4>
        <p>{{ $t('knowledgeSearch.regulations.description') }}</p>
      </div>
      <div class="regulations-status">
        <span v-if="regulationSource" class="status-badge ready">
          {{ $t('knowledgeSearch.regulations.ready') }}
        </span>
        <span v-else class="status-badge empty">
          {{ $t('knowledgeSearch.regulations.notCreated') }}
        </span>
      </div>
    </div>

    <!-- Section 1: Knowledge Source Management -->
    <div class="source-section">
      <div class="section-header">
        <h3>{{ $t('knowledgeSearch.title') }}</h3>
        <p>{{ $t('knowledgeSearch.description') }}</p>
      </div>

      <div class="sources-list">
        <div class="list-header">
          <span class="header-title">{{ $t('knowledgeSearch.sourcesList') }}</span>
          <button class="add-btn" @click="showCreateDialog = true">
            <component :is="PlusIcon" :size="16" />
            {{ $t('knowledgeSearch.addSource') }}
          </button>
        </div>

        <!-- Empty state -->
        <EmptyState
          v-if="sources.length === 0"
          icon="book-open"
          :title="$t('knowledgeSearch.empty')"
        />

        <!-- Source cards -->
        <div v-else class="sources-grid">
          <div
            v-for="source in sources"
            :key="source.id"
            :data-source-id="source.id"
          >
            <KnowledgeSourceCard
              :source="source"
              @toggle="toggleSource"
              @upload="uploadDocument"
              @delete="deleteSource"
              @sync="syncSource"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Section 2: Retrieval Configuration -->
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

    <!-- LLM Configuration -->
    <div class="config-section" v-if="config.default_mode !== 'direct'">
      <h4>{{ $t('knowledgeHub.llmConfig') }}</h4>

      <div class="form-group">
        <label class="toggle-label">
          <span>{{ $t('knowledgeHub.enableLLM') }}</span>
          <ToggleSwitch v-model="config.llm.enabled" @update:model-value="updateConfig" />
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

    <!-- Cache Configuration -->
    <div class="config-section">
      <h4>{{ $t('knowledgeHub.cache') }}</h4>
      <div class="form-group">
        <label class="toggle-label">
          <span>{{ $t('knowledgeHub.enableCache') }}</span>
          <ToggleSwitch v-model="config.cache.enabled" @update:model-value="updateConfig" />
        </label>
      </div>
      <div class="form-group">
        <label>{{ $t('knowledgeHub.cacheTTL') }} ({{ $t('knowledgeHub.cacheTTLUnit') }})</label>
        <input v-model.number="config.cache.ttl" type="number" @change="updateConfig" />
      </div>
      <button class="btn secondary" @click="refreshCache">
        {{ $t('knowledgeHub.refreshCache') }}
      </button>
    </div>

    <!-- Section 3: Test Retrieval -->
    <div class="retrieve-section">
      <h4 class="section-subtitle">{{ $t('knowledgeHub.testRetrieve') }}</h4>
      <div class="retrieve-form">
        <input
          v-model="testQuery"
          type="text"
          :placeholder="$t('knowledgeHub.queryPlaceholder')"
          class="query-input"
          @keyup.enter="testRetrieve"
        />
        <button class="btn primary" @click="testRetrieve" :disabled="testing">
          {{ testing ? $t('knowledgeHub.searching') : $t('knowledgeHub.search') }}
        </button>
      </div>

      <!-- Results display -->
      <div v-if="testResult" class="test-result">
        <pre>{{ testResult }}</pre>
      </div>
    </div>

    <!-- Create Source Dialog -->
    <Modal
      v-model="showCreateDialog"
      :title="$t('knowledgeSearch.createSource')"
      size="small"
      @confirm="createSource"
    >
      <div class="form-group">
        <label>{{ $t('knowledgeSearch.sourceName') }}</label>
        <input v-model="newSource.name" type="text" :placeholder="$t('knowledgeSearch.namePlaceholder')" />
      </div>

      <div class="form-group">
        <label>{{ $t('knowledgeSearch.sourceType') }}</label>
        <select v-model="newSource.source_type">
          <option value="local">{{ $t('knowledgeSearch.typeLocal') }}</option>
          <option value="database">{{ $t('knowledgeSearch.typeDatabase') }}</option>
          <option value="web_search">{{ $t('knowledgeSearch.typeWebSearch') }}</option>
        </select>
      </div>

      <!-- 本地文档需要输入目录路径 -->
      <div v-if="newSource.source_type === 'local'" class="form-group">
        <label>{{ $t('knowledgeSearch.localPath') }}</label>
        <div class="path-input-group">
          <input v-model="newSource.config.path" type="text" :placeholder="$t('knowledgeSearch.localPathPlaceholder')" />
          <button class="btn secondary" @click="browseServerDirectory" :disabled="browsingDir">
            <FolderOpen :size="16" />
            {{ browsingDir ? '...' : $t('knowledgeSearch.browse') }}
          </button>
        </div>
        <p class="path-hint">{{ $t('knowledgeSearch.pathHint') }}</p>
        <!-- Directory browsing results -->
        <div v-if="browseResults.length > 0" class="browse-results">
          <div
            v-for="entry in browseResults"
            :key="entry.path"
            class="browse-entry"
            @click="selectBrowsePath(entry)"
          >
            <component :is="entry.is_dir ? FolderOpen : FileText" :size="14" />
            <span>{{ entry.name }}</span>
            <span v-if="entry.is_dir" class="browse-dir">/</span>
          </div>
        </div>
      </div>

      <template #footer>
        <button class="btn secondary" @click="showCreateDialog = false">{{ $t('common.cancel') }}</button>
        <button class="btn primary" @click="createSource">{{ $t('common.save') }}</button>
      </template>
    </Modal>

    <!-- File Upload Input -->
    <input
      ref="fileInput"
      type="file"
      accept=".txt,.md,.pdf,.doc,.docx"
      style="display: none"
      @change="handleFileUpload"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Plus as PlusIcon,
  FolderOpen,
  FileText,
  ShieldCheck
} from 'lucide-vue-next'
import knowledgeHubApi, { type KnowledgeHubConfig, type SourceConfig } from '@/api/knowledgeHub'
import { useToast } from '@/composables/useToast'
import { EmptyState, Modal, ToggleSwitch } from '@/components/ui'
import KnowledgeSourceCard from '@/components/knowledge/KnowledgeSourceCard.vue'

const { t } = useI18n()
const toast = useToast()

// =====================
// Source Management
// =====================
const sources = ref<SourceConfig[]>([])
const showCreateDialog = ref(false)
const newSource = ref({
  name: '',
  source_type: 'local',
  config: {
    path: ''
  }
})
const fileInput = ref<HTMLInputElement | null>(null)
const uploadingSourceId = ref<string | null>(null)

// Server directory browsing
const browsingDir = ref(false)
const browseResults = ref<Array<{name: string, path: string, is_dir: boolean}>>([])

// =====================
// Regulations Source
// =====================
const regulationSource = computed(() => {
  return sources.value.find(s => s.tags && s.tags.includes('regulations'))
})

const scrollToRegulationSource = async () => {
  if (regulationSource.value) {
    // Already exists, scroll to its card
    const el = document.querySelector(`[data-source-id="${regulationSource.value.id}"]`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('highlight-pulse')
      setTimeout(() => el.classList.remove('highlight-pulse'), 2000)
    }
    return
  }
  // Create the regulations knowledge source
  try {
    await knowledgeHubApi.createSource({
      name: t('knowledgeSearch.regulations.title'),
      source_type: 'local',
      config: {},
      description: t('knowledgeSearch.regulations.description'),
      tags: ['regulations'],
    })
    toast.success(t('knowledgeSearch.regulations.created'))
    await loadSources()
  } catch (error) {
    console.error('Failed to create regulations source:', error)
    toast.error(t('knowledgeSearch.createError'))
  }
}

const loadSources = async () => {
  try {
    sources.value = await knowledgeHubApi.getSources()
  } catch (error) {
    console.error('Failed to load sources:', error)
    toast.error(t('knowledgeSearch.loadError'))
  }
}

const createSource = async () => {
  if (!newSource.value.name.trim()) {
    toast.error(t('knowledgeSearch.createError'))
    return
  }
  if (newSource.value.source_type === 'local' && !newSource.value.config.path?.trim()) {
    toast.error(t('knowledgeSearch.createError'))
    return
  }
  try {
    await knowledgeHubApi.createSource({
      name: newSource.value.name,
      source_type: newSource.value.source_type,
      config: newSource.value.source_type === 'local'
        ? { path: newSource.value.config.path }
        : {},
      local: newSource.value.source_type === 'local'
        ? { path: newSource.value.config.path }
        : undefined,
    })
    toast.success(t('knowledgeSearch.createSuccess'))
    await loadSources()
    showCreateDialog.value = false
    newSource.value = { name: '', source_type: 'local', config: { path: '' } }
    browseResults.value = []
  } catch (error) {
    console.error('Failed to create source:', error)
    toast.error(t('knowledgeSearch.createError'))
  }
}

const deleteSource = async (id: string) => {
  if (!confirm(t('knowledgeSearch.confirmDelete'))) return

  try {
    await knowledgeHubApi.deleteSource(id)
    sources.value = sources.value.filter(s => s.id !== id)
    toast.success(t('knowledgeSearch.deleteSuccess'))
  } catch (error) {
    console.error('Failed to delete source:', error)
    toast.error(t('knowledgeSearch.deleteError'))
  }
}

const syncSource = async (sourceId: string) => {
  try {
    const result = await knowledgeHubApi.syncSource(sourceId)
    toast.success(t('knowledgeSearch.syncSuccess') + ` (${result.chunks_count || 0} chunks)`)
    await loadSources()
  } catch (error: any) {
    console.error('Failed to sync source:', error)
    const errorMsg = error?.response?.data?.detail || error?.message || error?.toString() || 'Unknown error'
    toast.error(t('knowledgeSearch.syncError') + ': ' + errorMsg)
  }
}

const toggleSource = async (source: SourceConfig) => {
  try {
    await knowledgeHubApi.updateSource(source.id, { enabled: !source.enabled })
    source.enabled = !source.enabled
  } catch (error) {
    console.error('Failed to toggle source:', error)
    toast.error(t('knowledgeSearch.toggleError'))
    await loadSources()
  }
}

const uploadDocument = (sourceId: string) => {
  uploadingSourceId.value = sourceId
  fileInput.value?.click()
}

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file || !uploadingSourceId.value) return

  try {
    const result = await knowledgeHubApi.addDocument(uploadingSourceId.value, file)
    toast.success(t('knowledgeSearch.uploadSuccess', { count: result.chunks_added }))
    await loadSources()
  } catch (error) {
    console.error('Failed to upload document:', error)
    toast.error(t('knowledgeSearch.uploadError'))
  }

  // Reset
  target.value = ''
  uploadingSourceId.value = null
}

// =====================
// Server Directory Browsing
// =====================
const browseServerDirectory = async () => {
  const currentPath = newSource.value.config.path || '/'
  browsingDir.value = true
  try {
    browseResults.value = await knowledgeHubApi.browseDirectory(currentPath)
  } catch (error: any) {
    const detail = error?.response?.data?.detail || error?.message
    if (detail?.includes('not found') || detail?.includes('404')) {
      browseResults.value = []
    } else {
      console.error('Failed to browse directory:', error)
    }
  } finally {
    browsingDir.value = false
  }
}

const selectBrowsePath = (entry: {name: string, path: string, is_dir: boolean}) => {
  if (entry.is_dir) {
    newSource.value.config.path = entry.path
    browseResults.value = []
  }
}

// =====================
// Retrieval Configuration
// =====================
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
    max_memory_items: 100,
    cache_queries: true
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

// =====================
// Test Retrieval
// =====================
const testQuery = ref('')
const testing = ref(false)
const testResult = ref('')

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
  } catch (error: any) {
    console.error('Failed to retrieve:', error)
    const errorMsg = error?.response?.data?.detail || error?.message || error?.toString() || 'Unknown error'
    toast.error(t('knowledgeSearch.retrieveError'))
    testResult.value = 'Error: ' + errorMsg
  } finally {
    testing.value = false
  }
}

// Initialize - parallelize API calls
onMounted(async () => {
  await Promise.all([loadSources(), loadConfig()])
})
</script>

<style scoped>
.knowledge-search-system {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 16px;
}

/* Regulations Card */
.regulations-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.06) 0%, rgba(37, 99, 235, 0.1) 100%);
  border: 1px solid var(--color-primary);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.regulations-card:hover {
  border-color: var(--color-primary-hover, #2563eb);
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.15);
}

.regulations-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: var(--color-primary);
  color: white;
  border-radius: 10px;
  flex-shrink: 0;
}

.regulations-info {
  flex: 1;
  min-width: 0;
}

.regulations-info h4 {
  margin: 0 0 4px 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.regulations-info p {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.regulations-status {
  flex-shrink: 0;
}

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.ready {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.status-badge.empty {
  background: rgba(156, 163, 175, 0.1);
  color: #6b7280;
}

/* Highlight pulse for scroll target */
@keyframes highlight-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.3); }
  50% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.1); }
}

.highlight-pulse {
  animation: highlight-pulse 0.8s ease 2;
}

/* Section Headers */
.section-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-header h3 {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

.section-header p {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.section-subtitle {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 16px 0;
}

/* Source Section */
.source-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.header-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.add-btn:hover {
  background: var(--color-primary-hover);
}

.sources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

/* Config Section */
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

.path-input-group {
  display: flex;
  gap: 8px;
}

.path-input-group input {
  flex: 1;
}

.path-input-group .btn {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.path-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

/* Directory browsing */
.browse-results {
  margin-top: 8px;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--color-border-primary);
  border-radius: 6px;
  background: var(--color-bg-secondary);
}

.browse-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.browse-entry:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text-primary);
}

.browse-dir {
  color: var(--color-text-tertiary);
  margin-left: auto;
}

.toggle-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.btn.primary:hover {
  background: var(--color-primary-hover);
}

.btn.secondary {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Retrieve Section */
.retrieve-section {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: 8px;
  padding: 16px;
}

.retrieve-form {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.query-input {
  flex: 1;
  padding: 10px 12px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
  border-radius: 6px;
  font-size: 14px;
  color: var(--color-text-primary);
}

.query-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.test-result {
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
