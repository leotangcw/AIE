<template>
  <div class="experience-panel">
    <div class="section-header">
      <h3 class="section-title">经验学习</h3>
      <p class="section-desc">
        AIE 自动学习的技能和经验
      </p>
    </div>

    <!-- 学习统计 -->
    <div class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ skills.length }}</span>
        <span class="stat-label">已学习技能</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ totalUsage }}</span>
        <span class="stat-label">累计使用</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ avgConfidence }}%</span>
        <span class="stat-label">平均置信度</span>
      </div>
    </div>

    <!-- 技能列表 -->
    <div class="skills-list">
      <div v-if="skills.length === 0" class="empty-state">
        <p>暂无学习经验</p>
        <p class="hint">AIE 在与您互动过程中会自动学习</p>
      </div>

      <div v-for="skill in skills" :key="skill.id" class="skill-card">
        <div class="skill-header">
          <h4 class="skill-name">{{ skill.name }}</h4>
          <span class="skill-confidence" :class="getConfidenceClass(skill.confidence)">
            {{ Math.round(skill.confidence * 100) }}%
          </span>
        </div>

        <p class="skill-description">{{ skill.description }}</p>

        <div class="skill-meta">
          <span class="meta-item">
            <strong>使用次数:</strong> {{ skill.usage_count }}
          </span>
          <span class="meta-item">
            <strong>来源:</strong> {{ skill.source }}
          </span>
        </div>

        <div v-if="skill.trigger_conditions.length" class="skill-section">
          <h5>触发条件</h5>
          <ul>
            <li v-for="(cond, i) in skill.trigger_conditions" :key="i">{{ cond }}</li>
          </ul>
        </div>

        <div v-if="skill.action_steps.length" class="skill-section">
          <h5>操作步骤</h5>
          <ol>
            <li v-for="(step, i) in skill.action_steps" :key="i">{{ step }}</li>
          </ol>
        </div>

        <div class="skill-actions">
          <button class="btn-secondary" @click="applySkill(skill.id)">
            应用此技能
          </button>
        </div>
      </div>
    </div>

    <!-- 手动触发学习 -->
    <div class="learn-section">
      <h4>手动触发学习</h4>
      <p class="hint">当 AIE 的输出不符合预期时，提交反馈让 AIE 学习</p>

      <div class="form-group">
        <label>任务描述</label>
        <input v-model="learnForm.task_description" type="text" placeholder="描述您让 AIE 做的任务" />
      </div>

      <div class="form-group">
        <label>原始输出</label>
        <textarea v-model="learnForm.original_output" placeholder="AIE 原来的回答"></textarea>
      </div>

      <div class="form-group">
        <label>您的修改/反馈</label>
        <textarea v-model="learnForm.user_feedback" placeholder="您如何修改了回答"></textarea>
      </div>

      <div class="form-group">
        <label>最终输出</label>
        <textarea v-model="learnForm.final_output" placeholder="修改后的正确回答"></textarea>
      </div>

      <button class="btn-primary" @click="triggerLearn" :disabled="learning">
        {{ learning ? '学习中...' : '让 AIE 学习' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { experienceAPI, type LearnedSkill } from '@/api/experience'

const skills = ref<LearnedSkill[]>([])
const learning = ref(false)

const learnForm = ref({
  task_description: '',
  original_output: '',
  user_feedback: '',
  final_output: ''
})

const totalUsage = computed(() => skills.value.reduce((sum, s) => sum + s.usage_count, 0))
const avgConfidence = computed(() => {
  if (skills.value.length === 0) return 0
  const sum = skills.value.reduce((acc, s) => acc + s.confidence, 0)
  return Math.round(sum / skills.value.length * 100)
})

function getConfidenceClass(confidence: number): string {
  if (confidence >= 0.8) return 'high'
  if (confidence >= 0.5) return 'medium'
  return 'low'
}

async function loadSkills() {
  try {
    skills.value = await experienceAPI.getSkills()
  } catch (e) {
    console.error('Failed to load skills:', e)
  }
}

async function applySkill(skillId: string) {
  try {
    await experienceAPI.applySkill(skillId)
    await loadSkills()
  } catch (e) {
    console.error('Failed to apply skill:', e)
  }
}

async function triggerLearn() {
  if (!learnForm.value.task_description || !learnForm.value.final_output) {
    return
  }

  learning.value = true
  try {
    const newSkill = await experienceAPI.learn({
      task_description: learnForm.value.task_description,
      original_output: learnForm.value.original_output,
      user_feedback: learnForm.value.user_feedback,
      final_output: learnForm.value.final_output,
    })
    skills.value.unshift(newSkill)
    learnForm.value = {
      task_description: '',
      original_output: '',
      user_feedback: '',
      final_output: ''
    }
  } catch (e) {
    console.error('Failed to learn:', e)
  } finally {
    learning.value = false
  }
}

onMounted(loadSkills)
</script>

<style scoped>
.experience-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.section-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
}

.section-desc {
  font-size: 14px;
  color: var(--text-secondary, #666);
  margin: 0;
}

.stats-row {
  display: flex;
  gap: 16px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 24px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-primary, #007bff);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.skills-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.skill-card {
  padding: 16px;
  background: var(--bg-secondary, #f9f9f9);
  border-radius: 8px;
  border: 1px solid var(--border-color, #e0e0e0);
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.skill-name {
  margin: 0;
  font-size: 16px;
}

.skill-confidence {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.skill-confidence.high {
  background: #d4edda;
  color: #155724;
}

.skill-confidence.medium {
  background: #fff3cd;
  color: #856404;
}

.skill-confidence.low {
  background: #f8d7da;
  color: #721c24;
}

.skill-description {
  font-size: 14px;
  color: var(--text-secondary, #666);
  margin: 8px 0;
}

.skill-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-tertiary, #999);
  margin: 8px 0;
}

.skill-section {
  margin-top: 12px;
}

.skill-section h5 {
  font-size: 13px;
  margin: 0 0 8px 0;
  color: var(--text-primary, #333);
}

.skill-section ul, .skill-section ol {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--text-secondary, #666);
}

.skill-actions {
  margin-top: 12px;
}

.btn-secondary {
  padding: 8px 16px;
  background: var(--bg-tertiary, #e0e0e0);
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.learn-section {
  margin-top: 24px;
  padding: 20px;
  background: var(--bg-secondary, #f5f5f5);
  border-radius: 8px;
}

.learn-section h4 {
  margin: 0 0 8px 0;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  font-size: 13px;
  margin-bottom: 4px;
  font-weight: 500;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-color, #ddd);
  border-radius: 4px;
  font-size: 14px;
}

.form-group textarea {
  min-height: 80px;
  resize: vertical;
}

.btn-primary {
  padding: 10px 20px;
  background: var(--color-primary, #007bff);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-tertiary, #999);
}

.hint {
  font-size: 13px;
  color: var(--text-tertiary, #999);
  margin-top: 4px;
}
</style>
