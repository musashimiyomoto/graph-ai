import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

export type HistoryTabId = 'test-runs' | 'activity-log'

interface HistoryTab {
  id: HistoryTabId
  label: string
  content: ReactNode
}

interface HistoryOverlayProps {
  onClose: () => void
  tabs: HistoryTab[]
  defaultTabId: HistoryTabId
}

export function HistoryOverlay({ onClose, tabs, defaultTabId }: HistoryOverlayProps) {
  const [activeTabId, setActiveTabId] = useState<HistoryTabId>(defaultTabId)

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const activeTab = tabs.find((tab) => tab.id === activeTabId) ?? tabs[0]

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[var(--bg)] text-[var(--text)]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`pixel-tab ${tab.id === activeTabId ? 'is-active' : ''}`}
              onClick={() => setActiveTabId(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <button type="button" className="pixel-icon" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{activeTab?.content}</div>
    </div>
  )
}
