import type { ReactNode } from 'react'

interface HistoryOverlayProps {
  title: string
  onClose: () => void
  children: ReactNode
}

export function HistoryOverlay({ title, onClose, children }: HistoryOverlayProps) {
  return (
    <section className="pixel-panel flex min-h-0 flex-col p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="pixel-section-title">{title}</div>
        <button type="button" className="pixel-icon" onClick={onClose}>
          Back to editor
        </button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </section>
  )
}
