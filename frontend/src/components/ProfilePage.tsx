import { useState } from 'react'

import type { ApiError } from '../lib/types'
import { AccountSecuritySettings } from './AccountSecuritySettings'

interface ProfilePageProps {
  email: string
  onError: (err: ApiError) => void
  onPasswordChanged: () => void
  onLogout: () => void
  onDeleteAccount: () => void
}

export function ProfilePage({
  email,
  onError,
  onPasswordChanged,
  onLogout,
  onDeleteAccount,
}: ProfilePageProps) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <section className="pixel-panel grid min-h-0 grid-cols-[280px_1fr] overflow-hidden">
      <aside className="border-r border-white/10 p-6">
        <div className="pixel-section-title">Profile</div>
        <div className="mt-6 text-xs uppercase tracking-wider text-[var(--muted)]">
          Signed in as
        </div>
        <div className="mt-2 break-all text-lg text-[var(--text)]">{email}</div>

        <div className="mt-8 flex flex-col gap-2">
          <button type="button" className="pixel-button ghost" onClick={onLogout}>
            Log out
          </button>
          {confirmDelete ? (
            <div className="mt-3 border-2 border-[var(--danger)]/50 p-3">
              <div className="text-sm text-[var(--danger)]">
                Delete your account permanently?
              </div>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  className="pixel-button danger small flex-1"
                  onClick={onDeleteAccount}
                >
                  Delete
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
              className="pixel-button ghost danger"
              onClick={() => setConfirmDelete(true)}
            >
              Delete account
            </button>
          )}
        </div>
      </aside>
      <div className="pixel-scroll min-w-0 overflow-y-auto p-6">
        <div className="mb-6 border-b border-white/10 pb-4">
          <h1 className="text-2xl text-[var(--text)]">Security & sessions</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Change your password and manage browsers signed into your account.
          </p>
        </div>
        <AccountSecuritySettings
          onError={onError}
          onPasswordChanged={onPasswordChanged}
        />
      </div>
    </section>
  )
}
