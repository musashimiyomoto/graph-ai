import type { Execution } from '../lib/types'
import { ExecutionList } from './ExecutionList'

interface ExecutionHistoryProps {
  executions: Execution[]
  onClose: () => void
}

export function ExecutionHistory({
  executions,
  onClose,
}: ExecutionHistoryProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        className="pixel-panel modal-scroll w-full max-w-lg max-h-[80vh] overflow-y-auto"
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
        <ExecutionList executions={executions} />
      </div>
    </div>
  )
}
