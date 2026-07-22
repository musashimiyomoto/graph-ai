import { useMemo, useState } from 'react'

import { useChannelCatalog } from '../hooks/useChannelCatalog'
import type { ApiError } from '../lib/types'
import { AccountSecuritySettings } from './AccountSecuritySettings'
import { EmailSettings } from './EmailSettings'
import { Modal } from './Modal'
import { MCPServerSettings } from './MCPServerSettings'
import { ProviderSettings } from './ProviderSettings'
import { PostgresConnectionSettings } from './PostgresConnectionSettings'
import { TelegramSettings } from './TelegramSettings'
import { VectorCollectionSettings } from './VectorCollectionSettings'

interface SettingsModalProps {
  onClose: () => void
  onError: (err: ApiError) => void
  onPasswordChanged: () => void
}

interface SettingsSection {
  id: string
  label: string
  Component: (props: {
    onError: (err: ApiError) => void
    onPasswordChanged: () => void
  }) => React.JSX.Element
}

const CORE_SECTIONS_BEFORE_CHANNELS: SettingsSection[] = [
  { id: 'providers', label: 'LLM Providers', Component: ProviderSettings },
  { id: 'account', label: 'Account Security', Component: AccountSecuritySettings },
]

const CORE_SECTIONS_AFTER_CHANNELS: SettingsSection[] = [
  { id: 'postgres', label: 'PostgreSQL', Component: PostgresConnectionSettings },
  { id: 'mcp', label: 'MCP Servers', Component: MCPServerSettings },
  { id: 'vectors', label: 'Vector Collections', Component: VectorCollectionSettings },
]

const CHANNEL_SETTINGS_COMPONENTS: Partial<
  Record<string, SettingsSection['Component']>
> = {
  telegram: TelegramSettings,
  email: EmailSettings,
}

export function SettingsModal({
  onClose,
  onError,
  onPasswordChanged,
}: SettingsModalProps) {
  const [activeSectionId, setActiveSectionId] = useState<string>(
    CORE_SECTIONS_BEFORE_CHANNELS[0].id,
  )
  const { channelCatalog } = useChannelCatalog({ handleError: onError })
  const sections = useMemo<SettingsSection[]>(() => {
    const channelSections = channelCatalog.flatMap((channel) => {
      const settings = channel.settings
      if (!settings) {
        return []
      }
      const Component = CHANNEL_SETTINGS_COMPONENTS[settings.component_key]
      return Component
        ? [{ id: settings.key, label: settings.label, Component }]
        : []
    })
    return [
      ...CORE_SECTIONS_BEFORE_CHANNELS,
      ...channelSections,
      ...CORE_SECTIONS_AFTER_CHANNELS,
    ]
  }, [channelCatalog])

  return (
    <Modal onClose={onClose} maxWidth="max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <div className="pixel-section-title">Settings</div>
        <button type="button" className="pixel-icon" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="flex gap-4">
        <div className="flex w-40 shrink-0 flex-col gap-1">
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              className={`pixel-tab pixel-tab-vertical w-full ${
                section.id === activeSectionId ? 'is-active' : ''
              }`}
              onClick={() => setActiveSectionId(section.id)}
            >
              {section.label}
            </button>
          ))}
        </div>

        <div className="min-h-[22rem] min-w-0 flex-1 border-l border-white/10 pl-4">
          {/* All sections stay mounted for the lifetime of the modal instead of
              swapping in/out — otherwise every tab click unmounts the previous
              section (losing its state) and remounts the next one, which
              re-fires its data fetch and makes the panel visibly pop from an
              empty state to loaded content each time. Mounting once and just
              toggling visibility keeps switches instant and jump-free after
              the first load. */}
          {sections.map((section) => (
            <div key={section.id} className={section.id === activeSectionId ? '' : 'hidden'}>
              <section.Component
                onError={onError}
                onPasswordChanged={onPasswordChanged}
              />
            </div>
          ))}
        </div>
      </div>
    </Modal>
  )
}
