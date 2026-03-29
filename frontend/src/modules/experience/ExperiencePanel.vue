<template>
  <div class="experience-panel">
    <!-- Header -->
    <div class="panel-header">
      <h3 class="panel-title">{{ $t('experience.title') }}</h3>
      <p class="panel-desc">{{ $t('experience.description') }}</p>
    </div>

    <!-- Sub-tabs -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ $t(tab.labelKey) }}
      </button>
    </div>

    <!-- Tab: Overview -->
    <div v-if="activeTab === 'overview'" class="tab-content">
      <!-- Stats Cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <span class="stat-value">{{ stats.total }}</span>
          <span class="stat-label">{{ $t('experience.stats.totalTraces') }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ formatPercent(stats.success_rate) }}</span>
          <span class="stat-label">{{ $t('experience.stats.successRate') }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ formatPercent(stats.knowledge_rate) }}</span>
          <span class="stat-label">{{ $t('experience.stats.knowledgeRate') }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ formatDuration(stats.avg_duration) }}</span>
          <span class="stat-label">{{ $t('experience.stats.avgDuration') }}</span>
        </div>
      </div>

      <!-- Task Type Distribution -->
      <div v-if="taskTypeStats.length > 0" class="section-block">
        <h4 class="section-title">{{ $t('experience.taskDistribution') }}</h4>
        <div class="type-list">
          <div v-for="item in taskTypeStats" :key="item.type" class="type-item">
            <span class="type-name">{{ $t(`experience.taskTypes.${item.type}`) || item.type }}</span>
            <div class="type-bar-wrap">
              <div class="type-bar" :style="{ width: item.percent + '%' }" />
            </div>
            <span class="type-count">{{ item.count }}</span>
          </div>
        </div>
      </div>

      <!-- Recent Traces -->
      <div class="section-block">
        <h4 class="section-title">{{ $t('experience.recentTraces') }}</h4>
        <EmptyState
          v-if="recentTraces.length === 0 && !loading.traces"
          icon="activity"
          :title="$t('experience.noTraces')"
          :description="$t('experience.noTracesHint')"
        />
        <div v-else class="mini-trace-list">
          <div v-for="trace in recentTraces.slice(0, 5)" :key="trace.trace_id" class="mini-trace-item">
            <div class="mini-trace-left">
              <span :class="['outcome-dot', trace.outcome]" />
              <span class="mini-task-type">{{ trace.task_type }}</span>
            </div>
            <span class="mini-time">{{ formatTime(trace.started_at) }}</span>
          </div>
          <div v-if="loading.traces" class="loading-hint">{{ $t('common.loading') }}</div>
        </div>
      </div>
    </div>

    <!-- Tab: Activity Traces -->
    <div v-if="activeTab === 'traces'" class="tab-content">
      <!-- Filters -->
      <div class="filter-bar">
        <select v-model="filters.task_type" class="filter-select" @change="loadTraces">
          <option value="">{{ $t('experience.filters.allTypes') }}</option>
          <option value="knowledge_query">{{ $t('experience.taskTypes.knowledge_query') }}</option>
          <option value="content_creation">{{ $t('experience.taskTypes.content_creation') }}</option>
          <option value="web_search">{{ $t('experience.taskTypes.web_search') }}</option>
          <option value="coding">{{ $t('experience.taskTypes.coding') }}</option>
          <option value="general">{{ $t('experience.taskTypes.general') }}</option>
        </select>
        <select v-model="filters.outcome" class="filter-select" @change="loadTraces">
          <option value="">{{ $t('experience.filters.allOutcomes') }}</option>
          <option value="success">{{ $t('experience.filters.success') }}</option>
          <option value="failure">{{ $t('experience.filters.failure') }}</option>
        </select>
      </div>

      <!-- Trace List -->
      <EmptyState
        v-if="traces.length === 0 && !loading.traces"
        icon="activity"
        :title="$t('experience.noTraces')"
        :description="$t('experience.noTracesHint')"
      />
      <div v-else class="trace-list">
        <div
          v-for="trace in traces"
          :key="trace.trace_id"
          class="trace-card"
        >
          <div class="trace-summary" @click="toggleTraceDetail(trace.trace_id)">
            <div class="trace-left">
              <span :class="['outcome-dot', trace.outcome]" />
              <div class="trace-info">
                <span class="trace-task-type">{{ $t(`experience.taskTypes.${trace.task_type}`) || trace.task_type }}</span>
                <span class="trace-time">{{ formatTime(trace.started_at) }}</span>
              </div>
            </div>
            <div class="trace-right">
              <span class="trace-meta">
                {{ trace.tool_calls_count }} {{ $t('experience.toolCalls') }}
              </span>
              <span class="trace-meta">{{ formatDuration(trace.total_duration_ms) }}</span>
              <span class="expand-icon" :class="{ expanded: expandedTraceId === trace.trace_id }">&#9662;</span>
            </div>
          </div>

          <!-- Detail -->
          <div v-if="expandedTraceId === trace.trace_id" class="trace-detail">
            <div v-if="loading.detail" class="loading-hint">{{ $t('common.loading') }}</div>
            <template v-else-if="traceDetail">
              <!-- User message -->
              <div v-if="traceDetail.input?.user_message" class="detail-section">
                <h5>{{ $t('experience.userMessage') }}</h5>
                <p class="detail-text">{{ traceDetail.input.user_message }}</p>
              </div>

              <!-- Tool calls -->
              <div v-if="traceDetail.execution?.tool_calls?.length" class="detail-section">
                <h5>{{ $t('experience.toolCallSequence') }}</h5>
                <div class="tool-call-list">
                  <div
                    v-for="(tc, i) in traceDetail.execution.tool_calls"
                    :key="i"
                    :class="['tool-call-item', { failed: !tc.success }]"
                  >
                    <span class="tool-name">{{ tc.tool }}</span>
                    <span v-if="tc.result_summary" class="tool-result">{{ tc.result_summary }}</span>
                  </div>
                </div>
              </div>

              <!-- Knowledge usage -->
              <div v-if="traceDetail.knowledge_stage?.enterprise_knowledge_queried" class="detail-section">
                <h5>{{ $t('experience.knowledgeUsage') }}</h5>
                <div
                  v-for="(kr, i) in traceDetail.knowledge_stage.knowledge_results"
                  :key="i"
                  class="knowledge-item"
                >
                  <span class="kr-query">{{ kr.query }}</span>
                  <span class="kr-preview">{{ kr.result_preview }}</span>
                </div>
              </div>

              <div v-if="!traceDetail.input?.user_message && !traceDetail.execution?.tool_calls?.length" class="detail-empty">
                {{ $t('experience.noDetail') }}
              </div>
            </template>
          </div>
        </div>
        <div v-if="loading.traces" class="loading-hint">{{ $t('common.loading') }}</div>
      </div>
    </div>

    <!-- Tab: Skill Evolution -->
    <div v-if="activeTab === 'skills'" class="tab-content">
      <!-- Distill button -->
      <div class="skill-actions-bar">
        <button class="btn-primary" :disabled="loading.distill" @click="distillSkills">
          {{ loading.distill ? $t('experience.distilling') : $t('experience.distillNew') }}
        </button>
      </div>

      <!-- Distill result message -->
      <div v-if="distillMessage" class="distill-message" v-html="renderMarkdown(distillMessage)" />

      <!-- Candidate Skills -->
      <div class="section-block">
        <h4 class="section-title">{{ $t('experience.candidates') }}</h4>
        <EmptyState
          v-if="candidateSkills.length === 0 && !loading.candidates"
          icon="sparkles"
          :title="$t('experience.noCandidates')"
          :description="$t('experience.noCandidatesHint')"
        />
        <div v-else class="skill-list">
          <div v-for="skill in candidateSkills" :key="skill.name" class="skill-card">
            <div class="skill-info">
              <h5 class="skill-title">{{ skill.title || skill.name }}</h5>
              <p class="skill-desc">{{ skill.description }}</p>
              <div class="skill-meta">
                <span v-if="skill.confidence" class="meta-tag">
                  {{ $t('experience.confidence') }}: {{ Math.round(skill.confidence * 100) }}%
                </span>
                <span v-if="skill.created" class="meta-tag">{{ skill.created }}</span>
              </div>
            </div>
            <div class="skill-btns">
              <button class="btn-sm btn-outline" @click="viewCandidateDetail(skill.name)">
                {{ $t('common.view') || 'View' }}
              </button>
              <button class="btn-sm btn-success" :disabled="loading.promote === skill.name" @click="promoteSkill(skill.name)">
                {{ loading.promote === skill.name ? '...' : $t('experience.promote') }}
              </button>
              <button class="btn-sm btn-danger" :disabled="loading.reject === skill.name" @click="rejectSkill(skill.name)">
                {{ loading.reject === skill.name ? '...' : $t('experience.reject') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Official Skills -->
      <div class="section-block">
        <h4 class="section-title">{{ $t('experience.publishedSkills') }}</h4>
        <EmptyState
          v-if="officialSkills.length === 0 && !loading.skills"
          icon="award"
          :title="$t('experience.noPublishedSkills')"
        />
        <div v-else class="skill-list">
          <div v-for="skill in officialSkills" :key="skill.name" class="skill-card readonly">
            <div class="skill-info">
              <h5 class="skill-title">{{ skill.title || skill.name }}</h5>
              <p class="skill-desc">{{ skill.description }}</p>
            </div>
            <span class="published-badge">{{ $t('experience.published') }}</span>
          </div>
        </div>
      </div>

      <!-- Skill Detail Modal -->
      <Modal
        v-model="showSkillModal"
        :title="currentSkillDetail?.name || ''"
        size="large"
      >
        <div v-if="loading.skillDetail" class="loading-hint">{{ $t('common.loading') }}</div>
        <pre v-else-if="currentSkillDetail" class="skill-detail-content">{{ currentSkillDetail.content }}</pre>
      </Modal>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { EmptyState, Modal } from '@/components/ui'
import {
  experienceAPI,
  type TraceStats,
  type TraceSummary,
  type TraceDetail,
  type SkillMeta,
  type CandidateSkillDetail,
} from '@/api/experience'

const { t } = useI18n()

// ── Tabs ──
const tabs = [
  { key: 'overview', labelKey: 'experience.tabs.overview' },
  { key: 'traces', labelKey: 'experience.tabs.traces' },
  { key: 'skills', labelKey: 'experience.tabs.skills' },
]
const activeTab = ref('overview')

// ── Overview data ──
const stats = ref<TraceStats>({
  total: 0, success_count: 0, success_rate: 0,
  with_knowledge: 0, knowledge_rate: 0, avg_duration: 0, avg_tool_calls: 0,
})
const recentTraces = ref<TraceSummary[]>([])

// ── Traces data ──
const traces = ref<TraceSummary[]>([])
const expandedTraceId = ref<string | null>(null)
const traceDetail = ref<TraceDetail | null>(null)
const filters = ref({ task_type: '', outcome: '' })

// ── Skills data ──
const candidateSkills = ref<SkillMeta[]>([])
const officialSkills = ref<SkillMeta[]>([])
const showSkillModal = ref(false)
const currentSkillDetail = ref<CandidateSkillDetail | null>(null)
const distillMessage = ref('')

// ── Loading states ──
const loading = ref({
  stats: false,
  traces: false,
  detail: false,
  candidates: false,
  skills: false,
  distill: false,
  skillDetail: false,
  promote: null as string | null,
  reject: null as string | null,
})

// ── Computed ──
const taskTypeStats = computed(() => {
  const allTraces = recentTraces.value
  if (allTraces.length === 0) return []
  const counts: Record<string, number> = {}
  for (const t of allTraces) {
    counts[t.task_type] = (counts[t.task_type] || 0) + 1
  }
  const max = Math.max(...Object.values(counts))
  return Object.entries(counts)
    .map(([type, count]) => ({
      type,
      count,
      percent: Math.round((count / max) * 100),
    }))
    .sort((a, b) => b.count - a.count)
})

// ── Formatters ──
function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function formatDuration(ms: number): string {
  if (!ms || ms === 0) return '0s'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString()
}

function renderMarkdown(text: string): string {
  return text
    .replace(/## (.*)/g, '<strong>$1</strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}

// ── Data loaders ──
async function loadStats() {
  loading.value.stats = true
  try {
    stats.value = await experienceAPI.getTraceStats()
  } catch (e) {
    console.error('Failed to load trace stats:', e)
  } finally {
    loading.value.stats = false
  }
}

async function loadTraces() {
  loading.value.traces = true
  try {
    const params: Record<string, any> = { limit: 50 }
    if (filters.value.task_type) params.task_type = filters.value.task_type
    if (filters.value.outcome) params.outcome = filters.value.outcome
    traces.value = await experienceAPI.getTraces(params)
    if (recentTraces.value.length === 0) {
      recentTraces.value = traces.value
    }
  } catch (e) {
    console.error('Failed to load traces:', e)
  } finally {
    loading.value.traces = false
  }
}

async function loadCandidateSkills() {
  loading.value.candidates = true
  try {
    candidateSkills.value = await experienceAPI.getCandidateSkills()
  } catch (e) {
    console.error('Failed to load candidate skills:', e)
  } finally {
    loading.value.candidates = false
  }
}

async function loadOfficialSkills() {
  loading.value.skills = true
  try {
    officialSkills.value = await experienceAPI.getSkills()
  } catch (e) {
    console.error('Failed to load skills:', e)
  } finally {
    loading.value.skills = false
  }
}

// ── Actions ──
async function toggleTraceDetail(traceId: string) {
  if (expandedTraceId.value === traceId) {
    expandedTraceId.value = null
    traceDetail.value = null
    return
  }

  expandedTraceId.value = traceId
  traceDetail.value = null
  loading.value.detail = true
  try {
    traceDetail.value = await experienceAPI.getTraceDetail(traceId)
  } catch (e) {
    console.error('Failed to load trace detail:', e)
  } finally {
    loading.value.detail = false
  }
}

async function distillSkills() {
  loading.value.distill = true
  distillMessage.value = ''
  try {
    const result = await experienceAPI.distillSkills()
    distillMessage.value = result.message
    await loadCandidateSkills()
  } catch (e) {
    console.error('Failed to distill skills:', e)
  } finally {
    loading.value.distill = false
  }
}

async function viewCandidateDetail(name: string) {
  showSkillModal.value = true
  currentSkillDetail.value = null
  loading.value.skillDetail = true
  try {
    currentSkillDetail.value = await experienceAPI.getCandidateSkillDetail(name)
  } catch (e) {
    console.error('Failed to load candidate skill detail:', e)
  } finally {
    loading.value.skillDetail = false
  }
}

async function promoteSkill(name: string) {
  loading.value.promote = name
  try {
    await experienceAPI.promoteCandidateSkill(name)
    await loadCandidateSkills()
    await loadOfficialSkills()
  } catch (e) {
    console.error('Failed to promote skill:', e)
  } finally {
    loading.value.promote = null
  }
}

async function rejectSkill(name: string) {
  loading.value.reject = name
  try {
    await experienceAPI.rejectCandidateSkill(name)
    await loadCandidateSkills()
  } catch (e) {
    console.error('Failed to reject skill:', e)
  } finally {
    loading.value.reject = null
  }
}

// ── Tab switching ──
watch(activeTab, (tab) => {
  if (tab === 'overview') {
    loadStats()
  } else if (tab === 'traces') {
    loadTraces()
  } else if (tab === 'skills') {
    loadCandidateSkills()
    loadOfficialSkills()
  }
})

// ── Init ──
onMounted(() => {
  loadStats()
  loadTraces()
})
</script>

<style scoped>
.experience-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.panel-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.panel-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.panel-desc {
  font-size: 14px;
  color: var(--text-secondary, #666);
  margin: 0;
}

/* ── Tab bar ── */
.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  padding-bottom: 0;
}

.tab-btn {
  padding: 10px 20px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary, #666);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary, #333);
}

.tab-btn.active {
  color: var(--color-primary, #007bff);
  border-bottom-color: var(--color-primary, #007bff);
  font-weight: 500;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Stats grid ── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 12px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 8px;
  border: 1px solid var(--border-color, #e0e0e0);
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-primary, #007bff);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary, #666);
  margin-top: 4px;
}

/* ── Sections ── */
.section-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

/* ── Task type distribution ── */
.type-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.type-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.type-name {
  width: 120px;
  font-size: 13px;
  color: var(--text-primary, #333);
  flex-shrink: 0;
}

.type-bar-wrap {
  flex: 1;
  height: 8px;
  background: var(--bg-tertiary, #e0e0e0);
  border-radius: 4px;
  overflow: hidden;
}

.type-bar {
  height: 100%;
  background: var(--color-primary, #007bff);
  border-radius: 4px;
  transition: width 0.3s;
}

.type-count {
  width: 32px;
  text-align: right;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary, #666);
}

/* ── Mini trace list (overview) ── */
.mini-trace-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mini-trace-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 6px;
  font-size: 13px;
}

.mini-trace-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.outcome-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.outcome-dot.success {
  background: #22c55e;
}

.outcome-dot.failure {
  background: #ef4444;
}

.mini-task-type {
  color: var(--text-primary, #333);
}

.mini-time {
  font-size: 12px;
  color: var(--text-tertiary, #999);
}

/* ── Filter bar ── */
.filter-bar {
  display: flex;
  gap: 12px;
}

.filter-select {
  padding: 8px 12px;
  border: 1px solid var(--border-color, #ddd);
  border-radius: 6px;
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #333);
  font-size: 13px;
  cursor: pointer;
}

/* ── Trace list ── */
.trace-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trace-card {
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  overflow: hidden;
}

.trace-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s;
}

.trace-summary:hover {
  background: var(--bg-secondary, #f5f5f5);
}

.trace-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.trace-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trace-task-type {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #333);
}

.trace-time {
  font-size: 12px;
  color: var(--text-tertiary, #999);
}

.trace-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.trace-meta {
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.expand-icon {
  font-size: 12px;
  color: var(--text-tertiary, #999);
  transition: transform 0.2s;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

/* ── Trace detail ── */
.trace-detail {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-secondary, #f9f9f9);
}

.detail-section {
  margin-bottom: 12px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section h5 {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 6px 0;
  color: var(--text-secondary, #666);
}

.detail-text {
  font-size: 13px;
  color: var(--text-primary, #333);
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.tool-call-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-call-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 10px;
  background: var(--bg-primary, #fff);
  border-radius: 4px;
  border-left: 3px solid #22c55e;
}

.tool-call-item.failed {
  border-left-color: #ef4444;
}

.tool-name {
  font-size: 13px;
  font-weight: 500;
  font-family: monospace;
}

.tool-result {
  font-size: 12px;
  color: var(--text-secondary, #666);
  white-space: pre-wrap;
  word-break: break-word;
}

.knowledge-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 10px;
  background: var(--bg-primary, #fff);
  border-radius: 4px;
}

.kr-query {
  font-size: 13px;
  font-weight: 500;
}

.kr-preview {
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.detail-empty {
  font-size: 13px;
  color: var(--text-tertiary, #999);
  text-align: center;
  padding: 16px;
}

/* ── Skills ── */
.skill-actions-bar {
  display: flex;
  justify-content: flex-end;
}

.skill-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-secondary, #f5f5f5);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
}

.skill-card.readonly {
  opacity: 0.8;
}

.skill-info {
  flex: 1;
  min-width: 0;
}

.skill-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 4px 0;
}

.skill-desc {
  font-size: 13px;
  color: var(--text-secondary, #666);
  margin: 0 0 6px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-meta {
  display: flex;
  gap: 8px;
}

.meta-tag {
  font-size: 11px;
  color: var(--text-tertiary, #999);
  background: var(--bg-tertiary, #e8e8e8);
  padding: 2px 8px;
  border-radius: 4px;
}

.skill-btns {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 12px;
}

.published-badge {
  font-size: 11px;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
  padding: 3px 10px;
  border-radius: 4px;
  font-weight: 500;
  flex-shrink: 0;
}

/* ── Buttons ── */
.btn-primary {
  padding: 8px 20px;
  background: var(--color-primary, #007bff);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: opacity 0.15s;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sm {
  padding: 5px 12px;
  border: 1px solid var(--border-color, #ddd);
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: opacity 0.15s;
}

.btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  background: transparent;
  color: var(--text-primary, #333);
}

.btn-success {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  border-color: #22c55e;
}

.btn-danger {
  background: transparent;
  color: #ef4444;
  border-color: #ef4444;
}

/* ── Distill message ── */
.distill-message {
  padding: 16px;
  background: var(--bg-secondary, #f5f5f5);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary, #333);
}

.distill-message :deep(code) {
  background: var(--bg-tertiary, #e8e8e8);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}

/* ── Skill detail modal ── */
.skill-detail-content {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary, #333);
  background: var(--bg-secondary, #f5f5f5);
  padding: 16px;
  border-radius: 6px;
  max-height: 60vh;
  overflow-y: auto;
}

/* ── Loading ── */
.loading-hint {
  text-align: center;
  padding: 16px;
  font-size: 13px;
  color: var(--text-tertiary, #999);
}
</style>
