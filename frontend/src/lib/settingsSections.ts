import type { SettingsSectionId } from './types'

const SETTINGS_SECTION_LABELS: Record<SettingsSectionId, string> = {
  connections: 'Connections',
  providers: 'LLM Providers',
  telegram: 'Telegram Bots',
  email: 'Email Accounts',
  postgres: 'PostgreSQL',
  mcp: 'MCP Servers',
  vectors: 'Knowledge Sources',
}

export function getSettingsSectionLabel(sectionId: SettingsSectionId): string {
  return SETTINGS_SECTION_LABELS[sectionId]
}
