import { useEffect, useRef, useState } from 'react'

interface WorkflowActionsMenuProps {
  onEdit: () => void
  onDuplicate: () => void
  onExport: () => void
  onDelete: () => void
}

// Collapses the per-workflow Edit/Duplicate/Export/Delete actions behind one
// "..." toggle — four always-visible pixel-icon buttons don't fit the
// 280px sidebar column once the workflow name itself needs room to breathe.
export function WorkflowActionsMenu({
  onEdit,
  onDuplicate,
  onExport,
  onDelete,
}: WorkflowActionsMenuProps) {
  const [open, setOpen] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  function close(): void {
    setOpen(false)
    setConfirmingDelete(false)
  }

  useEffect(() => {
    if (!open) {
      return
    }
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as HTMLElement)) {
        close()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        className="pixel-icon"
        title="Workflow actions"
        onClick={() => setOpen((previous) => !previous)}
      >
        ⋯
      </button>
      {open ? (
        <div className="pixel-panel absolute right-0 top-full z-40 mt-1 flex min-w-[140px] flex-col gap-1 p-1">
          <button
            type="button"
            className="px-2 py-1 text-left text-xs hover:bg-white/5"
            onClick={() => {
              close()
              onEdit()
            }}
          >
            Edit
          </button>
          <button
            type="button"
            className="px-2 py-1 text-left text-xs hover:bg-white/5"
            onClick={() => {
              close()
              onDuplicate()
            }}
          >
            Duplicate
          </button>
          <button
            type="button"
            className="px-2 py-1 text-left text-xs hover:bg-white/5"
            onClick={() => {
              close()
              onExport()
            }}
          >
            Export
          </button>
          {confirmingDelete ? (
            <div className="flex gap-1">
              <button
                type="button"
                className="flex-1 px-2 py-1 text-left text-xs text-[var(--danger)] hover:bg-white/5"
                onClick={() => {
                  close()
                  onDelete()
                }}
              >
                Confirm delete
              </button>
              <button
                type="button"
                className="px-2 py-1 text-left text-xs text-[var(--muted)] hover:bg-white/5"
                onClick={() => setConfirmingDelete(false)}
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="px-2 py-1 text-left text-xs text-[var(--danger)] hover:bg-white/5"
              onClick={() => setConfirmingDelete(true)}
            >
              Delete
            </button>
          )}
        </div>
      ) : null}
    </div>
  )
}
