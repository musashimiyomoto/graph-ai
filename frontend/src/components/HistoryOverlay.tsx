import type { ReactNode } from 'react'

import { Modal } from './Modal'

export type HistoryTabId = 'test-runs' | 'activity-log'

interface HistoryOverlayProps {
  title: string
  onClose: () => void
  children: ReactNode
}

export function HistoryOverlay({ title, onClose, children }: HistoryOverlayProps) {
  return (
    <Modal onClose={onClose} maxWidth="max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <div className="pixel-section-title">{title}</div>
        <button type="button" className="pixel-icon" onClick={onClose}>
          ✕
        </button>
      </div>
      {/* Fixed height (rather than growing to content) so the panel's own
          flex layout can bound the scrollable turn/entry list — matching
          max-h-[80vh] on Modal's outer panel avoids a second, redundant
          scrollbar. */}
      <div className="flex h-[70vh] flex-col">{children}</div>
    </Modal>
  )
}
