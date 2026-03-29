/**
 * Knowledge System Type Definitions
 */

// =====================
// Source Types
// =====================
export const SourceType = {
  LOCAL: 'local',
  DATABASE: 'database',
  WEB_SEARCH: 'web_search'
} as const

export type SourceType = typeof SourceType[keyof typeof SourceType]

// =====================
// Retrieval Modes
// =====================
export const RetrievalMode = {
  DIRECT: 'direct',
  VECTOR: 'vector',
  LLM: 'llm',
  HYBRID: 'hybrid',
  GRAPH: 'graph'
} as const

export type RetrievalMode = typeof RetrievalMode[keyof typeof RetrievalMode]

// =====================
// Prompt Styles
// =====================
export const PromptStyle = {
  COMPRESS: 'compress',
  RESTATE: 'restate',
  REWORK: 'rework'
} as const

export type PromptStyle = typeof PromptStyle[keyof typeof PromptStyle]

// =====================
// Auth Types
// =====================
export const AuthType = {
  NONE: 'none',
  API_KEY: 'api_key',
  BEARER: 'bearer',
  BASIC: 'basic'
} as const

export type AuthType = typeof AuthType[keyof typeof AuthType]

// =====================
// Database Types
// =====================
export const DatabaseType = {
  MYSQL: 'mysql',
  POSTGRESQL: 'postgresql',
  SQLITE: 'sqlite',
  MONGODB: 'mongodb'
} as const

export type DatabaseType = typeof DatabaseType[keyof typeof DatabaseType]

// =====================
// Search Engine Types
// =====================
export const SearchEngine = {
  BING: 'bing',
  GOOGLE: 'google',
  DUCKDUCKGO: 'duckduckgo',
  BAIDU: 'baidu'
} as const

export type SearchEngine = typeof SearchEngine[keyof typeof SearchEngine]

// =====================
// Helper Functions
// =====================
export function isValidSourceType(value: string): value is SourceType {
  return Object.values(SourceType).includes(value as SourceType)
}

export function isValidRetrievalMode(value: string): value is RetrievalMode {
  return Object.values(RetrievalMode).includes(value as RetrievalMode)
}

export function isValidPromptStyle(value: string): value is PromptStyle {
  return Object.values(PromptStyle).includes(value as PromptStyle)
}
