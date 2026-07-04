import { useEffect, useState } from 'react'

import { getWorkflowVersions } from '../lib/api'
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
  const [versionNumbers, setVersionNumbers] = useState<Record<number, number>>(
    {},
  )

  const workflowId = executions[0]?.workflow_id ?? null

  useEffect(() => {
    if (workflowId === null) {
      return
    }
    let cancelled = false
    getWorkflowVersions(workflowId)
      .then((versions) => {
        if (cancelled) {
          return
        }
        const map: Record<number, number> = {}
        for (const version of versions) {
          map[version.id] = version.version
        }
        setVersionNumbers(map)
      })
      .catch(() => {
        // version labels are best-effort; ignore fetch failures
      })
    return () => {
      cancelled = true
    }
  }, [workflowId])

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
        <ExecutionList
          executions={executions}
          versionNumbers={versionNumbers}
        />
      </div>
    </div>
  )
}
