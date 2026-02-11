import { useEffect, useRef, useState } from 'react'

import type { RunInputPayload } from '../lib/types'

interface RunInputModalProps {
  initialValue: RunInputPayload
  loading: boolean
  canRun: boolean
  disabledReason: string | null
  onRun: (input: RunInputPayload) => void
  onClose: () => void
}

export function RunInputModal({
  initialValue,
  loading,
  canRun,
  disabledReason,
  onRun,
  onClose,
}: RunInputModalProps) {
  const [value, setValue] = useState(initialValue.value)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as HTMLElement)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div ref={ref} className="pixel-panel w-full max-w-md">
        <div className="mb-4 flex items-center justify-between">
          <div className="pixel-section-title">Run Input</div>
          <button type="button" className="pixel-icon" onClick={onClose}>
            ✕
          </button>
        </div>
        <label className="text-xs uppercase text-[var(--muted)]">
          Text Input
        </label>
        <textarea
          className="pixel-textarea mt-2 min-h-[200px]"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          disabled={!canRun || loading}
        />
        <div className="mt-2 text-xs text-[var(--muted)]">
          Format: txt. Payload will be sent as <code>{'{ "value": "..." }'}</code>.
        </div>
        {disabledReason ? (
          <div className="mt-3 text-xs text-red-400">{disabledReason}</div>
        ) : null}
        <button
          type="button"
          className="pixel-button small mt-4 w-full"
          disabled={loading || !canRun}
          onClick={() => onRun({ value })}
        >
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>
    </div>
  )
}
