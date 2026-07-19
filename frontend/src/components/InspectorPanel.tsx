import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Node as FlowNode } from 'reactflow'

import type { NodeCatalogItem, NodeType } from '../lib/types'
import { validateFields } from '../lib/validation'
import { NodeFieldsForm } from './NodeFieldsForm'

interface InspectorPanelProps {
  node: FlowNode | null
  nodeCatalog: NodeCatalogItem[]
  currentWorkflowId: number | null
  onSaveNode: (id: string, data: Record<string, unknown>) => Promise<boolean>
}

function SaveIndicator({
  state,
  onRetry,
}: {
  state: 'idle' | 'saving' | 'saved' | 'error'
  onRetry: () => void
}) {
  if (state === 'saving') {
    return <span className="text-xs text-[var(--muted)]">saving…</span>
  }
  if (state === 'saved') {
    return <span className="text-xs text-[var(--accent)]">saved ✓</span>
  }
  if (state === 'error') {
    return (
      <button
        type="button"
        className="text-xs text-[var(--danger)] underline"
        onClick={onRetry}
      >
        save failed — retry
      </button>
    )
  }
  return null
}

export function InspectorPanel({
  node,
  nodeCatalog,
  currentWorkflowId,
  onSaveNode,
}: InspectorPanelProps) {
  const nodeType = (node?.data?.nodeType as NodeType | undefined) ?? null
  const [draftData, setDraftData] = useState<Record<string, unknown>>({})
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>(
    'idle',
  )
  const lastSavedSnapshotRef = useRef<string>('')
  const draftDataRef = useRef<Record<string, unknown>>({})
  const nodeIdRef = useRef<string | null>(null)
  const validRef = useRef<boolean>(true)

  const catalogByType = useMemo(
    () => Object.fromEntries(nodeCatalog.map((item) => [item.type, item])) as Record<string, NodeCatalogItem>,
    [nodeCatalog],
  )

  const nodeSpec = nodeType ? catalogByType[nodeType] : undefined
  const fields = useMemo(() => nodeSpec?.fields ?? [], [nodeSpec])
  const allowedFieldNames = useMemo(
    () => new Set(fields.map((field) => field.name)),
    [fields],
  )

  const validationErrors = useMemo(
    () => validateFields(fields, draftData),
    [fields, draftData],
  )

  // Keep refs mirroring the latest draft/validity for flush-on-switch.
  useEffect(() => {
    draftDataRef.current = draftData
  }, [draftData])
  useEffect(() => {
    validRef.current = Object.keys(validationErrors).length === 0
  }, [validationErrors])

  useEffect(() => {
    let cancelled = false
    const rawData = node ? ((node.data as Record<string, unknown>) ?? {}) : {}
    const initialData = node
      ? Object.fromEntries(
          Object.entries(rawData).filter(([key]) => allowedFieldNames.has(key)),
        )
      : {}

    lastSavedSnapshotRef.current = node ? JSON.stringify(initialData) : ''
    nodeIdRef.current = node?.id ?? null

    void Promise.resolve().then(() => {
      if (cancelled) {
        return
      }
      setDraftData(initialData)
      setSaveState('idle')
    })

    return () => {
      cancelled = true
      // Flush the outgoing node's pending, valid changes before switching away,
      // so edits made within the debounce window are not lost.
      const outgoingId = nodeIdRef.current
      if (!outgoingId) {
        return
      }
      const pending = JSON.stringify(draftDataRef.current)
      if (pending !== lastSavedSnapshotRef.current && validRef.current) {
        void onSaveNode(outgoingId, draftDataRef.current)
      }
    }
  }, [allowedFieldNames, node, onSaveNode])

  useEffect(() => {
    if (!node) {
      return
    }

    const snapshot = JSON.stringify(draftData)
    if (snapshot === lastSavedSnapshotRef.current) {
      return
    }

    // Never persist invalid config; the inline errors tell the user why.
    if (Object.keys(validationErrors).length > 0) {
      return
    }

    const nodeId = node.id
    const timer = window.setTimeout(() => {
      setSaveState('saving')
      void onSaveNode(nodeId, draftData).then((ok) => {
        if (ok) {
          // Advance the saved snapshot only after a confirmed success so a
          // failed save is retried rather than silently dropped.
          lastSavedSnapshotRef.current = snapshot
          setSaveState('saved')
        } else {
          setSaveState('error')
        }
      })
    }, 400)

    return () => window.clearTimeout(timer)
  }, [draftData, node, onSaveNode, validationErrors])

  const retrySave = useCallback(() => {
    if (!node) {
      return
    }
    const snapshot = JSON.stringify(draftData)
    const nodeId = node.id
    setSaveState('saving')
    void onSaveNode(nodeId, draftData).then((ok) => {
      if (ok) {
        lastSavedSnapshotRef.current = snapshot
        setSaveState('saved')
      } else {
        setSaveState('error')
      }
    })
  }, [draftData, node, onSaveNode])

  return (
    <aside className="pixel-panel pixel-scroll flex h-full flex-col gap-6 overflow-y-auto">
      <div>
        <div className="flex items-center justify-between gap-2">
          <div className="pixel-section-title">Inspector</div>
          {node ? (
            <SaveIndicator state={saveState} onRetry={retrySave} />
          ) : null}
        </div>
        {!node ? (
          <div className="mt-4 text-xs text-[var(--muted)]">
            Select a node to configure its parameters.
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-3">
            <div className="text-xs text-[var(--muted)]">
              Type: <span className="text-[var(--accent)]">{nodeType}</span>
            </div>
            <NodeFieldsForm
              fields={fields}
              data={draftData}
              errors={validationErrors}
              currentWorkflowId={currentWorkflowId}
              onFieldChange={(_, next) => setDraftData(next)}
            />
          </div>
        )}
      </div>
    </aside>
  )
}
