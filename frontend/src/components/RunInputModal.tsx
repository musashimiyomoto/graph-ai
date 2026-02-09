import { useEffect, useRef, useState } from 'react'

interface RunInputModalProps {
  initialValue: string
  loading: boolean
  onRun: (input: string) => void
  onClose: () => void
}

export function RunInputModal({
  initialValue,
  loading,
  onRun,
  onClose,
}: RunInputModalProps) {
  const [value, setValue] = useState(initialValue)
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
        <textarea
          className="pixel-textarea min-h-[200px]"
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <div className="mt-2 text-xs text-[var(--muted)]">
          JSON payload will be sent to executions.
        </div>
        <button
          type="button"
          className="pixel-button small mt-4 w-full"
          disabled={loading}
          onClick={() => onRun(value)}
        >
          {loading ? 'Running...' : 'Run'}
        </button>
      </div>
    </div>
  )
}
