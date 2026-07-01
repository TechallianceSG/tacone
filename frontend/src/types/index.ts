export type SupportedLang = 'ja' | 'zh' | 'en'

export interface EntityOption {
  entity_id: string
  entity_code: string
  entity_name_en: string
  entity_name_ja: string
  entity_name_zh: string
  country: string
  status: string
}

export interface SessionInfo {
  session_id?: string
  session_id_suffix: string
  login_time: string
  login_time_jst: string
  logout_time: string
  logout_time_jst: string
  expires_at: string
  expires_at_jst: string
  ip_address: string
  browser: string
  device: string
  active: boolean
  entity: {
    entity_id: string
    entity_code: string
    entity_name_en: string
    entity_name_ja: string
    entity_name_zh: string
  }
  current_module_key: string
  current_module_path: string
  current_module_opened_at: string
  last_seen_at: string
  last_seen_at_jst: string
  last_activity_source: string
}

export interface UserInfo {
  user_id: string
  username: string
  display_name: string
  email: string
  user_type: string
  status?: string
  linked_employee_id: string
  employee_id: string
  employee_no: string
  employee_number?: string
  employee_name: string
  department: string
  department_id: string
  department_code: string
  department_name: string
  language_preference: string
  roles: string[]
  permissions: string[]
  entity_id?: string
  entity_code?: string
  entity_name?: string
  entity?: {
    entity_id: string
    entity_code: string
    entity_name_en: string
    entity_name_ja: string
    entity_name_zh: string
  }
  employee_context?: Record<string, any>
}

export interface ModuleInfo {
  module_key: string
  label: string
  labels: Record<string, string>
  description: string
  descriptions: Record<string, string>
  url: string
  status: string
  statuses: Record<string, string>
  required_permission: string
  enabled: boolean
}
