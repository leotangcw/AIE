<template>
  <div class="models-panel">
    <div class="panel-header">
      <h2 class="panel-title">{{ $t('settings.models.title') }}</h2>
      <p class="panel-description">{{ $t('settings.models.description') }}</p>
    </div>

    <!-- Model Configuration Tabs -->
    <div class="model-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['model-tab', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <component :is="tab.icon" :size="18" />
        <span class="tab-label">{{ $t(tab.label) }}</span>
      </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      <transition name="fade" mode="out-in">
        <!-- Main Agent Configuration -->
        <div v-if="activeTab === 'main'" key="main" class="tab-pane">
          <MainAgentConfig />
        </div>

        <!-- Sub Agent Configuration -->
        <div v-else-if="activeTab === 'sub'" key="sub" class="tab-pane">
          <SubAgentConfig />
        </div>

        <!-- Embedder Configuration -->
        <div v-else-if="activeTab === 'embedder'" key="embedder" class="tab-pane">
          <EmbedderConfig />
        </div>

        <!-- Enhanced Models Configuration -->
        <div v-else-if="activeTab === 'enhanced'" key="enhanced" class="tab-pane">
          <EnhancedModelsConfig />
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Bot as BotIcon,
  Sparkles as SparklesIcon,
  Binary as BinaryIcon,
  Wand2 as WandIcon
} from 'lucide-vue-next'
import MainAgentConfig from './MainAgentConfig.vue'
import SubAgentConfig from './SubAgentConfig.vue'
import EmbedderConfig from './EmbedderConfig.vue'
import EnhancedModelsConfig from './EnhancedModelsConfig.vue'

type ModelTabId = 'main' | 'sub' | 'embedder' | 'enhanced'

const activeTab = ref<ModelTabId>('main')

const tabs = computed(() => [
  { id: 'main' as ModelTabId, label: 'settings.models.mainAgent.shortLabel', icon: BotIcon },
  { id: 'sub' as ModelTabId, label: 'settings.models.subAgent.shortLabel', icon: SparklesIcon },
  { id: 'embedder' as ModelTabId, label: 'settings.models.embedder.shortLabel', icon: BinaryIcon },
  { id: 'enhanced' as ModelTabId, label: 'settings.models.enhanced.shortLabel', icon: WandIcon }
])
</script>

<style scoped>
.models-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.panel-header {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xl);
}

.panel-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.panel-description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0;
}

.model-tabs {
  display: flex;
  gap: var(--spacing-xs);
  padding-bottom: var(--spacing-md);
  border-bottom: 2px solid var(--border-color);
  margin-bottom: var(--spacing-xl);
  overflow-x: auto;
}

.model-tab {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-base);
  white-space: nowrap;
  flex-shrink: 0;
}

.model-tab:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.model-tab.active {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.1) 100%);
  color: var(--color-primary);
}

.tab-content {
  flex: 1;
  overflow-y: auto;
}

.tab-pane {
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .model-tabs {
    gap: 0;
  }

  .model-tab {
    flex: 1;
    flex-direction: column;
    gap: var(--spacing-xs);
    padding: var(--spacing-sm);
    text-align: center;
  }

  .tab-label {
    font-size: var(--font-size-xs);
  }
}
</style>
