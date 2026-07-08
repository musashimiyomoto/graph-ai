import { useState } from 'react'

import type { ApiError } from '../lib/types'
import { Modal } from './Modal'
import { ProviderSettings } from './ProviderSettings'
import { TelegramSettings } from './TelegramSettings'
import { VectorCollectionSettings } from './VectorCollectionSettings'

interface SettingsModalProps {
  onClose: () => void
  onError: (err: ApiError) => void
}

interface SettingsSection {
  id: string
  label: string
  Component: (props: { onError: (err: ApiError) => void }) => React.JSX.Element
}

// Adding a future integration means adding one entry here — no new header
// button, no new modal.
const SECTIONS: SettingsSection[] = [
  { id: 'providers', label: 'LLM Providers', Component: ProviderSettings },
  { id: 'telegram', label: 'Telegram Bots', Component: TelegramSettings },
  { id: 'vectors', label: 'Vector Collections', Component: VectorCollectionSettings },
]

export function SettingsModal({ onClose, onError }: SettingsModalProps) {
  const [activeSectionId, setActiveSectionId] = useState<string>(SECTIONS[0].id)

  const activeSection =
    SECTIONS.find((section) => section.id === activeSectionId) ?? SECTIONS[0]
  const ActiveComponent = activeSection.Component

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
          {SECTIONS.map((section) => (
            <button
              key={section.id}
              type="button"
              className={`pixel-tab w-full ${
                section.id === activeSectionId ? 'is-active' : ''
              }`}
              onClick={() => setActiveSectionId(section.id)}
            >
              {section.label}
            </button>
          ))}
        </div>

        <div className="min-w-0 flex-1 border-l border-white/10 pl-4">
          <ActiveComponent onError={onError} />
        </div>
      </div>
    </Modal>
  )
}
