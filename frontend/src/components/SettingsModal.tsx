import { useState } from 'react'

import type { ApiError } from '../lib/types'
import { EmailSettings } from './EmailSettings'
import { Modal } from './Modal'
import { ProviderSettings } from './ProviderSettings'
import { PostgresConnectionSettings } from './PostgresConnectionSettings'
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
  { id: 'email', label: 'Email Accounts', Component: EmailSettings },
  { id: 'postgres', label: 'PostgreSQL', Component: PostgresConnectionSettings },
  { id: 'vectors', label: 'Vector Collections', Component: VectorCollectionSettings },
]

export function SettingsModal({ onClose, onError }: SettingsModalProps) {
  const [activeSectionId, setActiveSectionId] = useState<string>(SECTIONS[0].id)

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
          {SECTIONS.map((section) => (
            <div key={section.id} className={section.id === activeSectionId ? '' : 'hidden'}>
              <section.Component onError={onError} />
            </div>
          ))}
        </div>
      </div>
    </Modal>
  )
}
