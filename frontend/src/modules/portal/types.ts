import type { Component } from 'vue'

export interface DashboardModule {
  /** Unique module key, used for tracking and CSS class */
  key: string
  /** Icon component from @element-plus/icons-vue */
  icon: Component
  /** i18n key for the card title */
  titleKey: string
  /** i18n key for the card description */
  descKey: string
  /** Vue Router path — use '#' for planned modules without a route */
  route: string
  /** Color theme suffix for CSS class (e.g. 'employee' → .employee-icon) */
  color: string
  /** 'active' = navigable card; 'planned' = disabled placeholder */
  status: 'active' | 'planned'
  /** Optional permission key to gate visibility */
  permission?: string
  /** i18n key for the action button label */
  actionKey: string
}
