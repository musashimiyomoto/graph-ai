import { useEffect } from 'react'
import type { ReactNode } from 'react'

export type HistoryTabId = 'test-runs' | 'activity-log'

interface HistoryOverlayProps {
  onClose: () => void
  children: ReactNode
}

export function HistoryOverlay({ onClose, children }: HistoryOverlayProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[var(--bg)] text-[var(--text)]">
      <div className="flex items-center justify-end border-b border-white/10 px-4 py-3">
        <button type="button" className="pixel-icon" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </div>
  )
}
