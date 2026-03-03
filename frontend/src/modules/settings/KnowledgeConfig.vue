<template>
  <div class="knowledge-config">
    <div class="section-header">
      <h3 class="section-title">{{ $t('settings.knowledge.title') }}</h3>
      <p class="section-desc">{{ $t('settings.knowledge.description') }}</p>
    </div>

    <!-- 知识源列表 -->
    <div class="sources-list">
      <div class="list-header">
        <span class="header-title">{{ $t('settings.knowledge.sourcesList') }}</span>
        <button class="add-btn" @click="showCreateDialog = true">
          <component :is="PlusIcon" :size="16" />
          {{ $t('settings.knowledge.addSource') }}
        </button>
      </div>

      <!-- 知识源为空 -->
      <div v-if="sources.length === 0" class="empty-state">
        <component :is="BookOpenIcon" :size="48" class="empty-icon" />
        <p>{{ $t('settings.knowledge.empty') }}</p>
      </div>

      <!-- 知识源卡片 -->
      <div v-else class="sources-grid">
        <div
          v-for="source in sources"
          :key="source.id"
          class="source-card"
          :class="{ disabled: !source.enabled }"
        >
          <div class="source-header">
            <div class="source-icon">
              <component :is="getSourceIcon(source.source_type)" :size="24" />
            </div>
            <div class="source-info">
              <h4 class="source-name">{{ source.name }}</h4>
              <span class="source-type-badge">{{ getSourceTypeLabel(source.source_type) }}</span>
            </div>
            <label class="toggle-switch">
              <input
                :checked="source.enabled"
                type="checkbox"
                @change="toggleSource(source)"
              >
              <span class="toggle-slider"></span>
            </label>
          </div>

          <div class="source-body">
            <div class="source-meta">
              <span v-if="source.last_sync" class="meta-item">
                <component :is="ClockIcon" :size="14" />
                {{ $t('settings.knowledge.lastSync') }}: {{ formatDate(source.last_sync) }}
              </span>
              <span v-else class="meta-item">
                <component :is="ClockIcon" :size="14" />
                {{ $t('settings.knowledge.neverSynced') }}
              </span>
            </div>
          </div>

          <div class="source-footer">
            <button class="action-btn" @click="uploadDocument(source.id)" :title="$t('settings.knowledge.upload')">
              <component :is="UploadIcon" :size="16" />
              {{ $t('settings.knowledge.uploadDocument') }}
            </button>
            <button class="action-btn danger" @click="deleteSource(source.id)" :title="$t('common.delete')">
              <component :is="TrashIcon" :size="16" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 检索测试 -->
    <div class="retrieve-section">
      <h4 class="section-subtitle">{{ $t('settings.knowledge.testRetrieve') }}</h4>
      <div class="retrieve-form">
        <input
          v-model="testQuery"
          type="text"
          :placeholder="$t('settings.knowledge.queryPlaceholder')"
          class="query-input"
        />
        <button class="btn primary" @click="testRetrieve" :disabled="retrieving">
          {{ retrieving ? $t('settings.knowledge.searching') : $t('settings.knowledge.search') }}
        </button>
      </div>

      <!-- 检索结果 -->
      <div v-if="retrieveResults.length > 0" class="results-list">
        <h5 class="results-title">{{ $t('settings.knowledge.results') }} ({{ retrieveResults.length }})</h5>
        <div
          v-for="(result, index) in retrieveResults"
          :key="result.id"
          class="result-card"
        >
          <div class="result-header">
            <span class="result-index">#{{ index + 1 }}</span>
            <span class="result-source">{{ result.source_id }}</span>
          </div>
          <div class="result-content">{{ result.content }}</div>
        </div>
      </div>
    </div>

    <!-- 创建知识源对话框 -->
    <div v-if="showCreateDialog" class="dialog-overlay" @click.self="showCreateDialog = false">
      <div class="dialog">
        <div class="dialog-header">
          <h3>{{ $t('settings.knowledge.createSource') }}</h3>
          <button class="close-btn" @click="showCreateDialog = false">
            <component :is="XIcon" :size="20" />
          </button>
        </div>

        <div class="dialog-body">
          <div class="form-group">
            <label>{{ $t('settings.knowledge.sourceName') }}</label>
            <input v-model="newSource.name" type="text" :placeholder="$t('settings.knowledge.namePlaceholder')" />
          </div>

          <div class="form-group">
            <label>{{ $t('settings.knowledge.sourceType') }}</label>
            <select v-model="newSource.source_type">
              <option value="local">{{ $t('settings.knowledge.typeLocal') }}</option>
              <option value="wiki">{{ $t('settings.knowledge.typeWiki') }}</option>
              <option value="database">{{ $t('settings.knowledge.typeDatabase') }}</option>
              <option value="api">{{ $t('settings.knowledge.typeApi') }}</option>
            </select>
          </div>
        </div>

        <div class="dialog-footer">
          <button class="btn secondary" @click="showCreateDialog = false">{{ $t('common.cancel') }}</button>
          <button class="btn primary" @click="createSource">{{ $t('common.save') }}</button>
        </div>
      </div>
    </div>

    <!-- 文件上传 -->
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
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Plus as PlusIcon,
  BookOpen as BookOpenIcon,
  FileText as FileTextIcon,
  Database as DatabaseIcon,
  Globe as GlobeIcon,
  Clock as ClockIcon,
  Upload as UploadIcon,
  Trash as TrashIcon,
  X as XIcon,
  Folder as FolderIcon
} from 'lucide-vue-next'
import knowledgeApi, { type KnowledgeSource, type KnowledgeChunk } from '@/api/knowledge'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const toast = useToast()

const sources = ref<KnowledgeSource[]>([])
const showCreateDialog = ref(false)
const testQuery = ref('')
const retrieving = ref(false)
const retrieveResults = ref<KnowledgeChunk[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const uploadingSourceId = ref<string | null>(null)

const newSource = ref({
  name: '',
  source_type: 'local'
})

const getSourceIcon = (type: string) => {
  const icons: Record<string, any> = {
    local: FolderIcon,
    wiki: GlobeIcon,
    database: DatabaseIcon,
    api: GlobeIcon
  }
  return icons[type] || FileTextIcon
}

const getSourceTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    local: t('settings.knowledge.typeLocal'),
    wiki: t('settings.knowledge.typeWiki'),
    database: t('settings.knowledge.typeDatabase'),
    api: t('settings.knowledge.typeApi')
  }
  return labels[type] || type
}

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return date.toLocaleString()
}

const loadSources = async () => {
  try {
    sources.value = await knowledgeApi.getSources()
  } catch (error) {
    console.error('Failed to load sources:', error)
    toast.error(t('settings.knowledge.loadError'))
  }
}

const createSource = async () => {
  try {
    await knowledgeApi.createSource(newSource.value.name, newSource.value.source_type)
    toast.success(t('settings.knowledge.createSuccess'))
    await loadSources()
    showCreateDialog.value = false
    newSource.value = { name: '', source_type: 'local' }
  } catch (error) {
    console.error('Failed to create source:', error)
    toast.error(t('settings.knowledge.createError'))
  }
}

const deleteSource = async (id: string) => {
  if (!confirm(t('settings.knowledge.confirmDelete'))) return

  try {
    await knowledgeApi.deleteSource(id)
    sources.value = sources.value.filter(s => s.id !== id)
    toast.success(t('settings.knowledge.deleteSuccess'))
  } catch (error) {
    console.error('Failed to delete source:', error)
    toast.error(t('settings.knowledge.deleteError'))
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
    toast.success(t('settings.knowledge.uploadSuccess', { count: result.chunks_added }))
    await loadSources()
  } catch (error) {
    console.error('Failed to upload document:', error)
    toast.error(t('settings.knowledge.uploadError'))
  }

  // Reset
  target.value = ''
  uploadingSourceId.value = null
}

const testRetrieve = async () => {
  if (!testQuery.value.trim()) return

  retrieving.value = true
  retrieveResults.value = []

  try {
    const result = await knowledgeApi.retrieve({
      query: testQuery.value,
      top_k: 5
    })
    retrieveResults.value = result.results
  } catch (error) {
    console.error('Failed to retrieve:', error)
    toast.error(t('settings.knowledge.retrieveError'))
  } finally {
    retrieving.value = false
  }
}

onMounted(() => {
  loadSources()
})
</script>

<style scoped>
.knowledge-config {
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

.section-subtitle {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-md) 0;
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

.sources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--spacing-md);
}

.source-card {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: all var(--transition-base);
}

.source-card:hover {
  border-color: var(--color-border-secondary);
  box-shadow: var(--shadow-sm);
}

.source-card.disabled {
  opacity: 0.6;
}

.source-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
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
  border-radius: var(--radius-md);
}

.source-info {
  flex: 1;
  min-width: 0;
}

.source-name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-xs) 0;
}

.source-type-badge {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  background: var(--color-bg-tertiary);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

.source-body {
  padding: var(--spacing-md);
}

.source-meta {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.source-footer {
  display: flex;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-secondary);
  border-top: 1px solid var(--color-border-primary);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 6px 12px;
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
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

/* Retrieve Section */
.retrieve-section {
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--color-border-primary);
}

.retrieve-form {
  display: flex;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.query-input {
  flex: 1;
  padding: 10px 12px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.query-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.results-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-sm) 0;
}

.result-card {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.result-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.result-index {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--color-primary);
}

.result-source {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.result-content {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
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
  max-width: 400px;
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
.form-group select {
  padding: 10px 12px;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--color-primary);
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

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
