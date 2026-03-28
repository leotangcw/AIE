/**
 * Settings 类型定义
 */

export interface ProviderMetadata {
    id: string
    name: string
    defaultApiBase?: string
    defaultModel?: string
    default_api_base?: string
    default_model?: string
}

export interface ProviderConfig {
    apiKey: string
    baseUrl?: string
    enabled: boolean
}

// 模型配置类型
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

export interface Settings {
    providers: Record<string, ProviderConfig>
    model: {
        provider: string
        model: string
        temperature: number
        max_tokens: number
        max_iterations: number
    }
    main_agent?: MainAgentConfig
    sub_agent?: SubAgentConfig
    enhanced_models?: EnhancedModelConfig[]
    workspace: string
    theme: 'light' | 'dark' | 'auto'
    language: 'zh-CN' | 'en-US' | 'auto'
    fontSize: 'small' | 'medium' | 'large'
}

export type SettingsTab = 'models' | 'persona' | 'workspace' | 'security' | 'channels' | 'rules'

export interface EmbeddingConfig {
    model: string
    dimension: number
    max_length: number
    device: string
    use_fp16: boolean
    cache_dir: string | null
    use_modelscope: boolean
    modelscope_endpoint: string | null
    api_fallback: {
        provider: string
        model: string
        api_key: string | null
        api_base: string | null
    } | null
}

export interface HeartbeatConfig {
    enabled: boolean
    channel: string
    chat_id: string
    schedule: string
    idle_threshold_hours: number
    quiet_start: number
    quiet_end: number
}

export interface PersonaConfig {
    ai_name: string
    user_name: string
    user_address?: string
    personality: string
    custom_personality: string
    max_history_messages: number
    heartbeat?: HeartbeatConfig
}
