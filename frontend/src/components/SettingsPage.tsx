import { useEffect, useMemo, useState } from 'react'

import { useChannelCatalog } from '../hooks/useChannelCatalog'
import type { ApiError, SettingsSectionId } from '../lib/types'
import { ConnectionSettings } from './ConnectionSettings'
import { EmailSettings } from './EmailSettings'
import { MCPServerSettings } from './MCPServerSettings'
import { PostgresConnectionSettings } from './PostgresConnectionSettings'
import { ProviderSettings } from './ProviderSettings'
import { TelegramSettings } from './TelegramSettings'
import { VectorCollectionSettings } from './VectorCollectionSettings'

interface SettingsPageProps {
  onError: (err: ApiError) => void
  initialSectionId?: SettingsSectionId
}

interface SettingsSection {
  id: string
  label: string
  description: string
  Component: (props: { onError: (err: ApiError) => void }) => React.JSX.Element
}

const CORE_SECTIONS_BEFORE_CHANNELS: SettingsSection[] = [
  {
    id: 'connections',
    label: 'Connections',
    description: 'Shared API keys and OAuth credentials.',
    Component: ConnectionSettings,
  },
  {
    id: 'providers',
    label: 'LLM Providers',
    description: 'Models and generation providers.',
    Component: ProviderSettings,
  },
]

const CORE_SECTIONS_AFTER_CHANNELS: SettingsSection[] = [
  {
    id: 'postgres',
    label: 'PostgreSQL',
    description: 'Database connections used by workflow nodes.',
    Component: PostgresConnectionSettings,
  },
  {
    id: 'mcp',
    label: 'MCP Servers',
    description: 'Remote tool servers available to workflows.',
    Component: MCPServerSettings,
  },
  {
    id: 'vectors',
    label: 'Knowledge Sources',
    description: 'Documents and tenant-scoped vector collections.',
    Component: VectorCollectionSettings,
  },
]

const CHANNEL_SETTINGS_COMPONENTS: Partial<
  Record<string, SettingsSection['Component']>
> = {
  telegram: TelegramSettings,
  email: EmailSettings,
}

export function SettingsPage({
  onError,
  initialSectionId = 'connections',
}: SettingsPageProps) {
  const [activeSectionId, setActiveSectionId] = useState(initialSectionId)
  const { channelCatalog } = useChannelCatalog({ handleError: onError })
  const sections = useMemo<SettingsSection[]>(() => {
    const channelSections = channelCatalog.flatMap((channel) => {
      const settings = channel.settings
      if (!settings) {
        return []
      }
      const Component = CHANNEL_SETTINGS_COMPONENTS[settings.component_key]
      return Component
        ? [
            {
              id: settings.key,
              label: settings.label,
              description: `${settings.label} channel accounts and delivery settings.`,
              Component,
            },
          ]
        : []
    })
    return [
      ...CORE_SECTIONS_BEFORE_CHANNELS,
      ...channelSections,
      ...CORE_SECTIONS_AFTER_CHANNELS,
    ]
  }, [channelCatalog])
  const activeSection =
    sections.find((section) => section.id === activeSectionId) ?? sections[0]

  useEffect(() => {
    setActiveSectionId(initialSectionId)
  }, [initialSectionId])

  return (
    <section className="pixel-panel grid min-h-0 grid-cols-[240px_1fr] overflow-hidden">
      <aside className="pixel-scroll overflow-y-auto border-r border-white/10 p-4">
        <div className="pixel-section-title">Settings</div>
        <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
          Configure workflow integrations and shared resources.
        </p>
        <nav className="mt-5 flex flex-col gap-1" aria-label="Settings sections">
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              className={`pixel-tab pixel-tab-vertical w-full ${
                section.id === activeSection?.id ? 'is-active' : ''
              }`}
              onClick={() => setActiveSectionId(section.id)}
            >
              {section.label}
            </button>
          ))}
        </nav>
      </aside>
      <div className="pixel-scroll min-w-0 overflow-y-auto p-6">
        {activeSection ? (
          <>
            <div className="mb-6 border-b border-white/10 pb-4">
              <h1 className="text-2xl text-[var(--text)]">{activeSection.label}</h1>
              <p className="mt-1 text-sm text-[var(--muted)]">
                {activeSection.description}
              </p>
            </div>
            <activeSection.Component onError={onError} />
          </>
        ) : null}
      </div>
    </section>
  )
}
