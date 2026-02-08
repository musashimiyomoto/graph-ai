import { useEffect, useRef } from 'react'

interface ContextMenuProps {
  label: string
  x: number
  y: number
  onDelete: () => void
  onClose: () => void
}

export function ContextMenu({
  label,
  x,
  y,
  onDelete,
  onClose,
}: ContextMenuProps) {
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
    <div
      ref={ref}
      className="fixed z-50 min-w-[160px] border-2 border-white/10 bg-[var(--panel)] shadow-lg"
      style={{ top: y, left: x }}
    >
      <div className="border-b border-white/10 px-3 py-2 text-xs text-[var(--muted)]">
        {label}
      </div>
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-sm text-[var(--danger)] hover:bg-white/5"
        onClick={onDelete}
      >
        Delete
      </button>
    </div>
  )
}
