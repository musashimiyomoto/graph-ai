import type { FormEvent } from 'react'
import { useState } from 'react'

import { changePassword } from '../lib/api'
import type { ApiError } from '../lib/types'
import { AuthSessionSettings } from './AuthSessionSettings'

interface AccountSecuritySettingsProps {
  onError: (error: ApiError) => void
  onPasswordChanged: () => void
}

export function AccountSecuritySettings({
  onError,
  onPasswordChanged,
}: AccountSecuritySettingsProps) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    if (newPassword !== confirmation) {
      setFormError('Passwords do not match.')
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await changePassword(currentPassword, newPassword)
      onPasswordChanged()
    } catch (error) {
      onError(error as ApiError)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section>
        <div className="pixel-section-title mb-3">Change password</div>
        <form className="pixel-form-stack" onSubmit={(event) => void handleSubmit(event)}>
          <label className="pixel-label">
            Current password
            <input
              className="pixel-input medium"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              maxLength={72}
              required
            />
          </label>
          <label className="pixel-label">
            New password
            <input
              className="pixel-input medium"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              minLength={8}
              maxLength={72}
              required
            />
          </label>
          <label className="pixel-label">
            Confirm new password
            <input
              className="pixel-input medium"
              type="password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              minLength={8}
              maxLength={72}
              required
            />
          </label>
          {formError ? <div className="pixel-error">{formError}</div> : null}
          <div className="text-xs text-[var(--muted)]">
            Changing your password signs out every browser session.
          </div>
          <button className="pixel-button" type="submit" disabled={saving}>
            {saving ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </section>

      <section className="border-t border-white/10 pt-5">
        <div className="pixel-section-title mb-3">Active sessions</div>
        <AuthSessionSettings onError={onError} />
      </section>
    </div>
  )
}
