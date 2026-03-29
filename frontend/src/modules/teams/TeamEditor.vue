<template>
  <teleport to="body">
    <div class="editor-overlay" @click.self="$emit('close')">
      <div class="editor-dialog">
        <!-- Dialog header -->
        <div class="dialog-header">
          <h3 class="dialog-title">{{ isEdit ? '编辑团队' : (templatePicked ? '创建团队' : '创建团队') }}</h3>
          <button class="close-btn" @click="$emit('close')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <!-- Form -->
        <div class="dialog-body">
          <!-- Template selection (create mode, before picking) -->
          <div v-if="!isEdit && !templatePicked" class="template-section">
            <p class="template-hint">选择一个预设模板快速创建，或从空白开始：</p>
            <div class="template-grid">
              <div
                v-for="tpl in presets"
                :key="tpl.id"
                class="template-card"
                @click="applyTemplate(tpl)"
              >
                <div class="tpl-header">
                  <span class="tpl-name">{{ tpl.name }}</span>
                  <span class="mode-badge" :class="`mode-${tpl.mode}`">
                    {{ modeLabels[tpl.mode] }}
                  </span>
                </div>
                <p class="tpl-desc">{{ tpl.description }}</p>
                <div class="tpl-agents">
                  <span v-for="a in tpl.agents" :key="a.id" class="tpl-agent-chip">{{ a.role }}</span>
                </div>
              </div>
            </div>
            <div class="template-blank" @click="templatePicked = true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              <span>从空白创建</span>
            </div>
          </div>

          <!-- Actual form (edit mode or after picking template) -->
          <template v-else>
          <!-- Back to templates (create mode) -->
          <button v-if="!isEdit" class="back-to-templates" @click="templatePicked = false">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
            返回模板选择
          </button>

          <!-- Name -->
          <div class="form-group">
            <label class="form-label">团队名称</label>
            <input
              v-model="form.name"
              class="form-input"
              type="text"
              placeholder="输入团队名称..."
            />
          </div>

          <!-- Mode -->
          <div class="form-group">
            <label class="form-label">运行模式</label>
            <select v-model="form.mode" class="form-select">
              <option value="pipeline">Pipeline（顺序执行）</option>
              <option value="graph">Graph（DAG 依赖图）</option>
              <option value="council">Council（圆桌讨论）</option>
            </select>
          </div>

          <!-- Toggles row -->
          <div class="form-row">
            <label class="toggle-label">
              <input v-model="form.enable_skills" type="checkbox" />
              <span>启用技能</span>
            </label>
            <label v-if="form.mode === 'council'" class="toggle-label">
              <input v-model="form.cross_review" type="checkbox" />
              <span>交叉评审</span>
            </label>
          </div>

          <!-- Members header -->
          <div class="members-header">
            <span class="members-title">成员列表 ({{ form.members.length }})</span>
            <div class="members-actions">
              <button class="small-btn" @click="addMember">+ 添加</button>
            </div>
          </div>

          <!-- Members list -->
          <div class="members-list">
            <div
              v-for="(member, idx) in form.members"
              :key="idx"
              class="member-card"
            >
              <div class="member-card-header">
                <span class="member-index">#{{ idx + 1 }}</span>
                <div class="member-card-actions">
                  <button
                    class="small-icon-btn"
                    :disabled="idx === 0"
                    title="上移"
                    @click="moveMember(idx, -1)"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
                  </button>
                  <button
                    class="small-icon-btn"
                    :disabled="idx === form.members.length - 1"
                    title="下移"
                    @click="moveMember(idx, 1)"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                  </button>
                  <button
                    class="small-icon-btn danger"
                    title="移除"
                    @click="removeMember(idx)"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  </button>
                </div>
              </div>

              <!-- Member fields -->
              <div class="member-fields">
                <div class="form-row">
                  <div class="form-group flex-1">
                    <label class="form-label-sm">ID</label>
                    <input v-model="member.id" class="form-input form-input-sm" type="text" placeholder="agent_1" />
                  </div>
                  <div class="form-group flex-1">
                    <label class="form-label-sm">角色</label>
                    <input v-model="member.role" class="form-input form-input-sm" type="text" placeholder="研究员" />
                  </div>
                </div>

                <div class="form-group">
                  <label class="form-label-sm">System Prompt</label>
                  <textarea v-model="member.system_prompt" class="form-textarea" rows="2" placeholder="系统提示词..." />
                </div>

                <div class="form-group">
                  <label class="form-label-sm">任务描述</label>
                  <textarea v-model="member.task" class="form-textarea" rows="2" placeholder="描述该 Agent 的任务..." />
                </div>

                <!-- Council: perspective -->
                <div v-if="form.mode === 'council'" class="form-group">
                  <label class="form-label-sm">视角 (Perspective)</label>
                  <textarea v-model="member.perspective" class="form-textarea" rows="1" placeholder="例如: 从技术可行性角度分析..." />
                </div>

                <!-- Graph: depends_on -->
                <div v-if="form.mode === 'graph'" class="form-group">
                  <label class="form-label-sm">依赖 (depends_on)</label>
                  <input
                    v-model="member.depends_on_str"
                    class="form-input form-input-sm"
                    type="text"
                    placeholder="agent_1, agent_2（逗号分隔的 Agent ID）"
                  />
                </div>

                <!-- Graph: condition -->
                <div v-if="form.mode === 'graph'" class="form-row">
                  <div class="form-group flex-1">
                    <label class="form-label-sm">条件 Key</label>
                    <input
                      v-model="member.condition_str"
                      class="form-input form-input-sm"
                      type="text"
                      placeholder="例如: approved"
                    />
                  </div>
                  <div class="form-group flex-1">
                    <label class="form-label-sm">条件 Value</label>
                    <input
                      v-model="member.condition_text"
                      class="form-input form-input-sm"
                      type="text"
                      placeholder="例如: true"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
          </template>
        </div>

        <!-- Dialog footer -->
        <div class="dialog-footer">
          <button class="btn btn-secondary" @click="$emit('close')">取消</button>
          <button class="btn btn-primary" :disabled="!canSave" @click="handleSave">
            {{ isEdit ? '保存修改' : '创建团队' }}
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { useTeamsStore } from '@/store/teams'
import type { AgentTeamResponse, AgentDefinition } from '@/api/agentTeams'

interface MemberForm {
  id: string
  role: string
  system_prompt: string
  task: string
  perspective: string
  depends_on_str: string
  condition_str: string
  condition_text: string
}

const props = defineProps<{
  team: AgentTeamResponse | null
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const teamsStore = useTeamsStore()
const saving = ref(false)
const templatePicked = ref(false)

const isEdit = computed(() => props.team !== null)

const modeLabels: Record<string, string> = {
  pipeline: 'Pipeline',
  graph: 'Graph',
  council: 'Council',
}

// Preset templates for quick creation
interface PresetTemplate {
  id: string
  name: string
  mode: 'pipeline' | 'graph' | 'council'
  description: string
  agents: { id: string; role: string; task: string; system_prompt?: string; perspective?: string }[]
}

const presets: PresetTemplate[] = [
  {
    id: 'research-write',
    name: '调研 + 撰写',
    mode: 'pipeline',
    description: '先调研再撰写，适合需要信息收集后输出的场景',
    agents: [
      { id: 'researcher', role: '调研员', task: '深入调研给定主题，收集关键信息和数据' },
      { id: 'writer', role: '撰稿人', task: '基于调研结果，撰写完整、结构清晰的内容' },
    ],
  },
  {
    id: 'parallel-expert',
    name: '并行专家',
    mode: 'graph',
    description: '多个专家并行分析后汇总，适合多角度分析场景',
    agents: [
      { id: 'analyst_a', role: '技术分析师', task: '从技术角度分析问题和方案' },
      { id: 'analyst_b', role: '业务分析师', task: '从业务和用户角度分析需求和影响' },
      { id: 'summarizer', role: '汇总者', task: '综合各方观点，输出最终分析报告', depends_on: '["analyst_a", "analyst_b"]' } as any,
    ],
  },
  {
    id: 'council-debate',
    name: '圆桌讨论',
    mode: 'council',
    description: '多位专家从不同视角讨论，适合需要辩证思维的复杂决策',
    agents: [
      { id: 'optimist', role: '乐观派', task: '从积极可行的角度分析方案', perspective: '关注优势和机会' },
      { id: 'critic', role: '质疑派', task: '挑战方案的假设和风险', perspective: '关注风险和隐患' },
      { id: 'mediator', role: '调和派', task: '寻找平衡点和折中方案', perspective: '关注平衡和可行性' },
    ],
  },
]

interface TeamForm {
  name: string
  mode: 'pipeline' | 'graph' | 'council'
  enable_skills: boolean
  cross_review: boolean
  members: MemberForm[]
}

const form = reactive<TeamForm>({
  name: '',
  mode: 'pipeline',
  enable_skills: false,
  cross_review: false,
  members: [],
})

// Initialize form from team prop (edit mode)
if (props.team) {
  templatePicked.value = true
  form.name = props.team.name
  form.mode = props.team.mode
  form.enable_skills = props.team.enable_skills
  form.cross_review = props.team.cross_review
  form.members = props.team.agents.map(a => ({
    id: a.id,
    role: a.role,
    system_prompt: a.system_prompt || '',
    task: a.task,
    perspective: a.perspective || '',
    depends_on_str: (a.depends_on || []).join(', '),
    condition_str: a.condition ? Object.keys(a.condition).join(', ') : '',
    condition_text: a.condition ? Object.values(a.condition).join(', ') : '',
  }))
}

function applyTemplate(tpl: PresetTemplate) {
  form.name = tpl.name
  form.mode = tpl.mode
  form.enable_skills = false
  form.cross_review = tpl.mode === 'council'
  form.members = tpl.agents.map(a => ({
    id: a.id,
    role: a.role,
    system_prompt: a.system_prompt || '',
    task: a.task,
    perspective: a.perspective || '',
    depends_on_str: (a as any).depends_on ? JSON.parse((a as any).depends_on).join(', ') : '',
    condition_str: '',
    condition_text: '',
  }))
  templatePicked.value = true
}

function createEmptyMember(): MemberForm {
  return {
    id: `agent_${form.members.length + 1}`,
    role: '',
    system_prompt: '',
    task: '',
    perspective: '',
    depends_on_str: '',
    condition_str: '',
    condition_text: '',
  }
}

function addMember() {
  form.members.push(createEmptyMember())
}

function removeMember(idx: number) {
  form.members.splice(idx, 1)
}

function moveMember(idx: number, direction: number) {
  const newIdx = idx + direction
  if (newIdx < 0 || newIdx >= form.members.length) return
  const temp = form.members[idx]
  form.members[idx] = form.members[newIdx]
  form.members[newIdx] = temp
}

const canSave = computed(() => {
  return form.name.trim().length > 0 && form.members.length > 0
})

function parseDependsOn(str: string): string[] {
  if (!str || !str.trim()) return []
  return str.split(',').map(s => s.trim()).filter(Boolean)
}

function buildCondition(conditionStr: string, conditionText: string): Record<string, string> | undefined {
  if (!conditionStr.trim() && !conditionText.trim()) return undefined
  const keys = conditionStr.split(',').map(s => s.trim()).filter(Boolean)
  const values = conditionText.split(',').map(s => s.trim()).filter(Boolean)
  const result: Record<string, string> = {}
  for (let i = 0; i < keys.length; i++) {
    result[keys[i]] = values[i] || ''
  }
  return Object.keys(result).length > 0 ? result : undefined
}

function buildAgents(): AgentDefinition[] {
  return form.members.map(m => ({
    id: m.id,
    role: m.role,
    system_prompt: m.system_prompt || undefined,
    task: m.task,
    perspective: m.perspective || undefined,
    depends_on: form.mode === 'graph' ? parseDependsOn(m.depends_on_str) : undefined,
    condition: form.mode === 'graph' ? buildCondition(m.condition_str, m.condition_text) : undefined,
  }))
}

async function handleSave() {
  if (!canSave.value || saving.value) return
  saving.value = true

  try {
    const agents = buildAgents()

    if (isEdit.value && props.team) {
      await teamsStore.updateTeam(props.team.id, {
        name: form.name,
        mode: form.mode,
        agents,
        enable_skills: form.enable_skills,
        cross_review: form.cross_review,
      })
    } else {
      await teamsStore.createTeam({
        name: form.name,
        mode: form.mode,
        agents,
        enable_skills: form.enable_skills,
        cross_review: form.cross_review,
      })
    }

    emit('saved')
  } catch (e) {
    console.error('Failed to save team:', e)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.editor-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.editor-dialog {
  width: 90%;
  max-width: 720px;
  max-height: 85vh;
  background: var(--bg-primary, #1a1a2e);
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

/* Header */
.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color, #2a2a3a);
  flex-shrink: 0;
}

.dialog-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
  margin: 0;
}

.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-tertiary, #888);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary, #e0e0e0);
}

/* Body */
.dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

/* Form groups */
.form-group {
  margin-bottom: 12px;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary, #aaa);
  margin-bottom: 4px;
}

.form-label-sm {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary, #888);
  margin-bottom: 3px;
}

.form-input,
.form-select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 6px;
  background: var(--bg-secondary, #16162a);
  color: var(--text-primary, #e0e0e0);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.form-input:focus,
.form-select:focus {
  border-color: var(--accent-color, #4f8ff7);
}

.form-input::placeholder {
  color: var(--text-tertiary, #555);
}

.form-select option {
  background: var(--bg-secondary, #16162a);
  color: var(--text-primary, #e0e0e0);
}

.form-textarea {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 6px;
  background: var(--bg-secondary, #16162a);
  color: var(--text-primary, #e0e0e0);
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s;
  resize: vertical;
  font-family: inherit;
  box-sizing: border-box;
  line-height: 1.4;
}

.form-textarea:focus {
  border-color: var(--accent-color, #4f8ff7);
}

.form-textarea::placeholder {
  color: var(--text-tertiary, #555);
}

.form-input-sm {
  padding: 6px 8px;
  font-size: 12px;
}

/* Form row */
.form-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.flex-1 {
  flex: 1;
  min-width: 0;
}

/* Toggle */
.toggle-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #aaa);
  cursor: pointer;
}

.toggle-label input[type="checkbox"] {
  accent-color: var(--accent-color, #4f8ff7);
}

/* Members section */
.members-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color, #2a2a3a);
}

.members-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
}

.small-btn {
  padding: 4px 10px;
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 5px;
  background: transparent;
  color: var(--accent-color, #4f8ff7);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s;
}

.small-btn:hover {
  background: rgba(79, 143, 247, 0.1);
}

/* Members list */
.members-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.member-card {
  background: var(--bg-secondary, #16162a);
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 8px;
  padding: 10px 12px;
}

.member-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.member-index {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-color, #4f8ff7);
}

.member-card-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.small-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-tertiary, #888);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.small-icon-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary, #e0e0e0);
}

.small-icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.small-icon-btn.danger:hover {
  color: #d9534f;
  background: rgba(217, 83, 79, 0.1);
}

.member-fields .form-group {
  margin-bottom: 8px;
}

.member-fields .form-group:last-child {
  margin-bottom: 0;
}

/* Footer */
.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--border-color, #2a2a3a);
  flex-shrink: 0;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary, #aaa);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
}

.btn-primary {
  background: var(--accent-color, #4f8ff7);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

/* Scrollbar */
.dialog-body::-webkit-scrollbar {
  width: 6px;
}

.dialog-body::-webkit-scrollbar-track {
  background: transparent;
}

.dialog-body::-webkit-scrollbar-thumb {
  background: var(--border-color, #2a2a3a);
  border-radius: 3px;
}

/* Template selection */
.template-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.template-hint {
  font-size: 13px;
  color: var(--text-secondary, #aaa);
  margin: 0;
}

.template-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.template-card {
  background: var(--bg-secondary, #16162a);
  border: 1px solid var(--border-color, #2a2a3a);
  border-radius: 8px;
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.template-card:hover {
  border-color: var(--accent-color, #4f8ff7);
  background: rgba(79, 143, 247, 0.05);
}

.tpl-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.tpl-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
}

.tpl-desc {
  font-size: 12px;
  color: var(--text-tertiary, #888);
  margin: 0 0 8px;
  line-height: 1.4;
}

.tpl-agents {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tpl-agent-chip {
  font-size: 11px;
  color: var(--text-secondary, #aaa);
  background: rgba(255, 255, 255, 0.04);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-color, #2a2a3a);
}

.template-blank {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border: 1px dashed var(--border-color, #2a2a3a);
  border-radius: 8px;
  color: var(--text-tertiary, #888);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}

.template-blank:hover {
  border-color: var(--accent-color, #4f8ff7);
  color: var(--accent-color, #4f8ff7);
}

.back-to-templates {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
  border: none;
  background: transparent;
  color: var(--text-tertiary, #888);
  font-size: 12px;
  cursor: pointer;
  margin-bottom: 8px;
  transition: color 0.15s;
}

.back-to-templates:hover {
  color: var(--accent-color, #4f8ff7);
}
</style>
