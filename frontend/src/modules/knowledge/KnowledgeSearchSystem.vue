<template>
  <div class="knowledge-search-system">
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
          <KnowledgeSourceCard
            v-for="source in sources"
            :key="source.id"
            :source="source"
            @toggle="toggleSource"
            @upload="uploadDocument"
            @delete="deleteSource"
            @sync="syncSource"
          />
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
          <option value="wiki">{{ $t('knowledgeSearch.typeWiki') }}</option>
          <option value="database">{{ $t('knowledgeSearch.typeDatabase') }}</option>
          <option value="api">{{ $t('knowledgeSearch.typeApi') }}</option>
          <option value="web">{{ $t('knowledgeSearch.typeWeb') }}</option>
        </select>
      </div>

      <!-- 本地文档需要输入目录路径 -->
      <div v-if="newSource.source_type === 'local'" class="form-group">
        <label>{{ $t('knowledgeSearch.localPath') }}</label>
        <div class="path-input-group">
          <input v-model="newSource.config.path" type="text" :placeholder="$t('knowledgeSearch.localPathPlaceholder')" readonly />
          <button class="btn secondary" @click="selectFolder">
            <FolderOpen :size="16" />
            {{ $t('knowledgeSearch.browse') }}
          </button>
        </div>
        <p class="path-hint">{{ $t('knowledgeSearch.pathHint') }}</p>
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

    <!-- Folder Picker Input -->
    <input
      ref="folderInput"
      type="file"
      webkitdirectory
      style="display: none"
      @change="handleFolderSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Plus as PlusIcon,
  FolderOpen as FolderOpenIcon
} from 'lucide-vue-next'
import knowledgeApi, { type KnowledgeSource } from '@/api/knowledge'
import knowledgeHubApi, { type KnowledgeHubConfig } from '@/api/knowledgeHub'
import { useToast } from '@/composables/useToast'
import { EmptyState, Modal, ToggleSwitch } from '@/components/ui'
import KnowledgeSourceCard from '@/components/knowledge/KnowledgeSourceCard.vue'

const { t } = useI18n()
const toast = useToast()

// =====================
// Source Management
// =====================
const sources = ref<KnowledgeSource[]>([])
const showCreateDialog = ref(false)
const newSource = ref({
  name: '',
  source_type: 'local',
  config: {
    path: ''
  }
})
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)
const uploadingSourceId = ref<string | null>(null)

const loadSources = async () => {
  try {
    sources.value = await knowledgeApi.getSources()
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
  // 本地文档类型需要目录路径
  if (newSource.value.source_type === 'local' && !newSource.value.config.path?.trim()) {
    toast.error(t('knowledgeSearch.createError'))
    return
  }
  try {
    const config = newSource.value.source_type === 'local'
      ? { path: newSource.value.config.path }
      : {}
    await knowledgeApi.createSource(newSource.value.name, newSource.value.source_type, config)
    toast.success(t('knowledgeSearch.createSuccess'))
    await loadSources()
    showCreateDialog.value = false
    newSource.value = { name: '', source_type: 'local', config: { path: '' } }
  } catch (error) {
    console.error('Failed to create source:', error)
    toast.error(t('knowledgeSearch.createError'))
  }
}

const selectFolder = () => {
  folderInput.value?.click()
}

const handleFolderSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (!files || files.length === 0) return

  // Get the first selected item's path (webkitRelativePath contains the directory)
  const firstFile = files[0]
  let folderPath = ''

  // Try to get path from webkitRelativePath (format: "folder_name/file.txt")
  if (firstFile.webkitRelativePath) {
    const parts = firstFile.webkitRelativePath.split('/')
    if (parts.length > 0) {
      // Get the directory path from the first file
      // We need to find the common parent directory
      const dirParts = parts.slice(0, -1)
      if (dirParts.length > 0) {
        folderPath = dirParts.join('/')
      }
    }
  }

  // Fallback: construct path from the File object's name and the relative path
  // For security reasons, browsers may not expose full paths, but we try our best
  if (!folderPath && firstFile.webkitRelativePath) {
    folderPath = firstFile.webkitRelativePath.replace(/\/[^\/]+$/, '')
  }

  // Update the path in newSource
  newSource.value.config.path = folderPath || firstFile.name

  // Reset input
  target.value = ''
}

const deleteSource = async (id: string) => {
  if (!confirm(t('knowledgeSearch.confirmDelete'))) return

  try {
    await knowledgeApi.deleteSource(id)
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
    toast.success(t('knowledgeSearch.syncSuccess'))
    await loadSources()
  } catch (error: any) {
    console.error('Failed to sync source:', error)
    const errorMsg = error?.response?.data?.detail || error?.message || error?.toString() || 'Unknown error'
    toast.error(t('knowledgeSearch.syncError') + ': ' + errorMsg)
  }
}

const toggleSource = async (source: KnowledgeSource) => {
  // Toggle is handled by backend - just reload
  await loadSources()
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
    const result = await knowledgeApi.addDocument(uploadingSourceId.value, file)
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
    max_memory_items: 100
  },
  sources: [],
  storage_dir: 'memory/knowledge_hub'
})

const modes = [
  { value: 'direct', labelKey: 'knowledgeHub.directMode' },
  { value: 'llm', labelKey: 'knowledgeHub.llmMode' },
  { value: 'hybrid', labelKey: 'knowledgeHub.hybridMode' }
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

.source-card {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s;
}

.source-card:hover {
  border-color: var(--color-border-secondary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.source-card.disabled {
  opacity: 0.6;
}

.source-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--color-border-primary);
}

.source-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: var(--color-primary-light);
  color: var(--color-primary);
  border-radius: 8px;
}

.source-info {
  flex: 1;
  min-width: 0;
}

.source-name {
  font-size: 16px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin: 0 0 4px 0;
}

.source-type-badge {
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-bg-tertiary);
  padding: 2px 8px;
  border-radius: 4px;
}

.source-body {
  padding: 16px;
}

.source-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.source-footer {
  display: flex;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--color-bg-secondary);
  border-top: 1px solid var(--color-border-primary);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
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
