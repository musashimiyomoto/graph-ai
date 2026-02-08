import { useEffect, useRef, useState } from 'react'

interface UserMenuProps {
  email: string
  onLogout: () => void
  onDeleteAccount: () => void
}

export function UserMenu({ email, onLogout, onDeleteAccount }: UserMenuProps) {
  const [open, setOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as HTMLElement)) {
        setOpen(false)
        setConfirmDelete(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        className="pixel-user cursor-pointer transition-colors hover:border-[var(--accent)]"
        onClick={() => {
          setOpen((prev) => !prev)
          setConfirmDelete(false)
        }}
      >
        Profile
      </button>
      {open ? (
        <div className="absolute right-0 top-full z-50 mt-2 min-w-[200px] border-2 border-white/10 bg-[var(--panel)] shadow-lg">
          <div className="border-b border-white/10 px-4 py-3 text-xs text-[var(--muted)]">
            {email}
          </div>
          <button
            type="button"
            className="flex w-full items-center px-4 py-3 text-sm text-[var(--text)] transition-colors hover:bg-white/5"
            onClick={() => {
              setOpen(false)
              onLogout()
            }}
          >
            Logout
          </button>
          {confirmDelete ? (
            <div className="border-t border-white/10 px-4 py-3">
              <div className="mb-2 text-xs text-[var(--danger)]">
                This cannot be undone.
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="pixel-button small flex-1"
                  style={{ background: 'var(--danger)' }}
                  onClick={() => {
                    setOpen(false)
                    setConfirmDelete(false)
                    onDeleteAccount()
                  }}
                >
                  Confirm
                </button>
                <button
                  type="button"
                  className="pixel-button ghost small flex-1"
                  onClick={() => setConfirmDelete(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="flex w-full items-center border-t border-white/10 px-4 py-3 text-sm text-[var(--danger)] transition-colors hover:bg-[rgba(255,86,120,0.1)]"
              onClick={() => setConfirmDelete(true)}
            >
              Delete account
            </button>
          )}
        </div>
      ) : null}
    </div>
  )
}
