import { useEffect, useRef } from 'react'

import type { Execution } from '../lib/types'
import { ExecutionList } from './ExecutionList'

interface ExecutionHistoryProps {
  executions: Execution[]
  loading: boolean
  onClose: () => void
}

export function ExecutionHistory({
  executions,
  loading,
  onClose,
}: ExecutionHistoryProps) {
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
      <div
        ref={ref}
        className="pixel-panel w-full max-w-lg max-h-[80vh] overflow-y-auto"
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="pixel-section-title">Execution History</div>
          <button
            type="button"
            className="pixel-icon"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
        <ExecutionList executions={executions} loading={loading} />
      </div>
    </div>
  )
}
