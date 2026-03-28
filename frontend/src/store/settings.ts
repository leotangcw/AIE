/**
 * Settings 状态管理
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsAPI, type Settings } from '@/api'

export interface ProviderConfig {
    enabled: boolean
    api_key?: string
    api_base?: string
}

export interface ModelConfig {
    provider: string
    model: string
    temperature: number
    max_tokens: number
    max_iterations: number
}

export interface MainAgentConfig {
    provider: string
    model: string
    temperature: number
    max_tokens: number
    max_iterations: number
    enabled: boolean
    advanced_params: Record<string, any>
    api_key?: string
    api_base?: string
}

export interface SubAgentConfig {
    enabled: boolean
    provider: string
    model: string
    max_concurrent: number
    temperature: number
    max_tokens: number
    api_key?: string
    api_base?: string
    advanced_params: Record<string, any>
}

export interface EnhancedModelConfig {
    id: string
    model_type: string
    provider: string
    model: string
    enabled: boolean
    description: string
    capabilities: string[]
    priority: number
    temperature?: number
    max_tokens?: number
    api_key?: string
    api_base?: string
    advanced_params?: Record<string, any>
}

export interface WorkspaceConfig {
    path: string
}

export interface SecurityConfig {
    // API 密钥加密
    api_key_encryption_enabled: boolean

    // 危险命令检测
    dangerous_commands_blocked: boolean
    custom_deny_patterns: string[]

    // 命令白名单
    command_whitelist_enabled: boolean
    custom_allow_patterns: string[]

    // 审计日志
    audit_log_enabled: boolean

    // 其他安全选项
    command_timeout: number
    max_output_length: number
    restrict_to_workspace: boolean
}

export const useSettingsStore = defineStore('settings', () => {
    // State
    const settings = ref<Settings | null>(null)
    const loading = ref(false)
    const saving = ref(false)
    const testing = ref(false)
    const error = ref<string | null>(null)

    /**
     * 加载设置
     */
    async function loadSettings() {
        loading.value = true
        error.value = null
        try {
            const response = await settingsAPI.get()
            console.log('[SettingsStore] Loaded settings:', response)
            console.log('[SettingsStore] Providers:', response.providers)
            console.log('[SettingsStore] Model provider:', response.model?.provider)
            console.log('[SettingsStore] Enhanced models:', response.enhanced_models)
            console.log('[SettingsStore] Sub agent:', response.sub_agent)
            settings.value = response
        } catch (err: any) {
            error.value = err.message || 'Failed to load settings'
            throw err
        } finally {
            loading.value = false
        }
    }

    /**
     * 保存设置
     */
    async function saveSettings(newSettings: Partial<Settings>) {
        saving.value = true
        error.value = null
        try {
            const response = await settingsAPI.update(newSettings)
            settings.value = response
        } catch (err: any) {
            error.value = err.message || 'Failed to save settings'
            throw err
        } finally {
            saving.value = false
        }
    }

    /**
     * 测试连接
     */
    async function testConnection(provider: string, apiKey: string, apiBase?: string, model?: string) {
        testing.value = true
        error.value = null
        try {
            const response = await settingsAPI.testConnection({
                provider,
                api_key: apiKey,
                api_base: apiBase,
                model
            })
            return response.success
        } catch (err: any) {
            error.value = err.message || 'Connection test failed'
            throw err
        } finally {
            testing.value = false
        }
    }

    /**
     * 更新提供商配置
     */
    function updateProvider(provider: string, config: ProviderConfig) {
        if (settings.value) {
            settings.value.providers[provider] = config
        }
    }

    /**
     * 更新模型配置
     */
    function updateModel(config: Partial<ModelConfig>) {
        if (settings.value) {
            settings.value.model = { ...settings.value.model, ...config }
        }
    }

    /**
     * 更新主 Agent 配置
     */
    function updateMainAgent(config: Partial<MainAgentConfig>) {
        if (settings.value && settings.value.main_agent) {
            settings.value.main_agent = { ...settings.value.main_agent, ...config }
        }
    }

    /**
     * 更新子 Agent 配置
     */
    function updateSubAgent(config: Partial<SubAgentConfig>) {
        if (settings.value && settings.value.sub_agent) {
            settings.value.sub_agent = { ...settings.value.sub_agent, ...config }
        }
    }

    /**
     * 更新增强模型列表
     */
    function updateEnhancedModels(models: EnhancedModelConfig[]) {
        if (settings.value) {
            settings.value.enhanced_models = models
        }
    }

    /**
     * 添加增强模型
     */
    function addEnhancedModel(model: EnhancedModelConfig) {
        if (settings.value) {
            if (!settings.value.enhanced_models) {
                settings.value.enhanced_models = []
            }
            settings.value.enhanced_models.push(model)
        }
    }

    /**
     * 删除增强模型
     */
    function removeEnhancedModel(modelId: string) {
        if (settings.value && settings.value.enhanced_models) {
            const index = settings.value.enhanced_models.findIndex(m => m.id === modelId)
            if (index >= 0) {
                settings.value.enhanced_models.splice(index, 1)
            }
        }
    }

    /**
     * 更新工作空间配置
     */
    function updateWorkspace(config: WorkspaceConfig) {
        if (settings.value) {
            settings.value.workspace = config
        }
    }

    /**
     * 更新安全配置
     */
    function updateSecurity(config: SecurityConfig) {
        if (settings.value) {
            settings.value.security = config
            // 自动保存到后端
            saveSettings({ security: config })
        }
    }

    return {
        // State
        settings,
        loading,
        saving,
        testing,
        error,

        // Actions
        loadSettings,
        saveSettings,
        testConnection,
        updateProvider,
        updateModel,
        updateMainAgent,
        updateSubAgent,
        updateEnhancedModels,
        addEnhancedModel,
        removeEnhancedModel,
        updateWorkspace,
        updateSecurity
    }
})
