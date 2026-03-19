<template>
  <div
    class="source-card"
    :class="{ disabled: !source.enabled }"
  >
    <div class="source-header">
      <div class="source-icon">
        <component :is="getIcon(source.source_type)" :size="24" />
      </div>
      <div class="source-info">
        <h4 class="source-name">{{ source.name }}</h4>
        <span class="source-type-badge">{{ getTypeLabel(source.source_type) }}</span>
      </div>
      <ToggleSwitch
        :model-value="source.enabled"
        @update:model-value="$emit('toggle', source)"
      />
    </div>

    <div class="source-body">
      <div class="source-meta">
        <span v-if="source.last_sync" class="meta-item">
          <Clock :size="14" />
          {{ lastSyncLabel }}: {{ formattedDate(source.last_sync) }}
        </span>
        <span v-else class="meta-item">
          <Clock :size="14" />
          {{ neverSyncedLabel }}
        </span>
      </div>
    </div>

    <div class="source-footer">
      <button class="action-btn" @click="$emit('upload', source.id)">
        <Upload :size="16" />
        {{ uploadLabel }}
      </button>
      <button class="action-btn danger" @click="$emit('delete', source.id)">
        <Trash :size="16" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  FileText,
  Database,
  Globe,
  Folder,
  Clock,
  Upload,
  Trash
} from 'lucide-vue-next'
import { formatDate } from '@/utils/time'
import ToggleSwitch from '@/components/ui/ToggleSwitch.vue'

interface KnowledgeSource {
  id: string
  name: string
  source_type: string
  enabled: boolean
  last_sync: string | null
}

interface Props {
  source: KnowledgeSource
}

const props = defineProps<Props>()

defineEmits<{
  toggle: [source: KnowledgeSource]
  upload: [id: string]
  delete: [id: string]
}>()

const { t } = useI18n()

const lastSyncLabel = computed(() => t('knowledgeSearch.lastSync'))
const neverSyncedLabel = computed(() => t('knowledgeSearch.neverSynced'))
const uploadLabel = computed(() => t('knowledgeSearch.uploadDocument'))

const getIcon = (type: string) => {
  const icons: Record<string, any> = {
    local: Folder,
    wiki: Globe,
    database: Database,
    api: Globe,
    web: Globe
  }
  return icons[type] || FileText
}

const getTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    local: t('knowledgeSearch.typeLocal'),
    wiki: t('knowledgeSearch.typeWiki'),
    database: t('knowledgeSearch.typeDatabase'),
    api: t('knowledgeSearch.typeApi'),
    web: t('knowledgeSearch.typeWeb')
  }
  return labels[type] || type
}

const formattedDate = (dateStr: string) => {
  return formatDate(dateStr)
}
</script>

<style scoped>
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
</style>
