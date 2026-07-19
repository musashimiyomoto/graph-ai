import type { FormEvent } from 'react'
import { useState } from 'react'

type AuthMode = 'login' | 'register' | 'forgot' | 'reset'

interface AuthScreenProps {
  loading: boolean
  error: string | null
  notice: string | null
  pendingVerificationEmail: string | null
  resetPasswordToken: string | null
  onLogin: (email: string, password: string) => void
  onRegister: (email: string, password: string) => void
  onResendVerification: (email: string) => void
  onRequestPasswordReset: (email: string) => void
  onResetPassword: (password: string) => void
  onClearNotice: () => void
}

export function AuthScreen({
  loading,
  error,
  notice,
  pendingVerificationEmail,
  resetPasswordToken,
  onLogin,
  onRegister,
  onResendVerification,
  onRequestPasswordReset,
  onResetPassword,
  onClearNotice,
}: AuthScreenProps) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const activeMode: AuthMode = resetPasswordToken ? 'reset' : mode

  function selectMode(nextMode: AuthMode): void {
    setMode(nextMode)
    setPassword('')
    setPasswordConfirmation('')
    setFormError(null)
    onClearNotice()
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    setFormError(null)

    if (activeMode === 'forgot') {
      onRequestPasswordReset(email.trim())
      return
    }
    if (activeMode === 'register' || activeMode === 'reset') {
      if (password !== passwordConfirmation) {
        setFormError('Passwords do not match.')
        return
      }
    }
    if (activeMode === 'reset') {
      onResetPassword(password)
    } else if (activeMode === 'login') {
      onLogin(email.trim(), password)
    } else {
      onRegister(email.trim(), password)
    }
  }

  const needsEmail = activeMode !== 'reset'
  const needsPassword = activeMode !== 'forgot'

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col items-center justify-center gap-8 px-6 py-12">
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="text-xs uppercase tracking-[0.2em] text-[var(--accent)]">
            Graph AI
          </span>
          <h1 className="font-pixel text-3xl uppercase">Pixel Flow Studio</h1>
        </div>

        <div className="pixel-panel w-full max-w-md">
          {activeMode !== 'reset' ? (
            <div className="flex gap-2">
              <button
                type="button"
                className={`pixel-tab ${activeMode === 'login' ? 'is-active' : ''}`}
                onClick={() => selectMode('login')}
              >
                Login
              </button>
              <button
                type="button"
                className={`pixel-tab ${activeMode === 'register' ? 'is-active' : ''}`}
                onClick={() => selectMode('register')}
              >
                Register
              </button>
            </div>
          ) : (
            <div className="pixel-section-title">Choose a new password</div>
          )}

          {activeMode === 'forgot' ? (
            <div className="mt-5 text-sm text-[var(--muted)]">
              Enter your account email. The response is the same whether or not an
              account exists.
            </div>
          ) : null}

          <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit}>
            {needsEmail ? (
              <label className="pixel-label">
                Email
                <input
                  className="pixel-input"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@graph.ai"
                  required
                />
              </label>
            ) : null}
            {needsPassword ? (
              <label className="pixel-label">
                {activeMode === 'reset' ? 'New password' : 'Password'}
                <input
                  className="pixel-input"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="At least 8 characters"
                  minLength={8}
                  maxLength={72}
                  required
                />
              </label>
            ) : null}
            {activeMode === 'register' || activeMode === 'reset' ? (
              <label className="pixel-label">
                Confirm password
                <input
                  className="pixel-input"
                  type="password"
                  value={passwordConfirmation}
                  onChange={(event) => setPasswordConfirmation(event.target.value)}
                  placeholder="Repeat password"
                  minLength={8}
                  maxLength={72}
                  required
                />
              </label>
            ) : null}

            {notice ? <div className="pixel-card text-sm">{notice}</div> : null}
            {formError || error ? (
              <div className="pixel-error">{formError ?? error}</div>
            ) : null}
            {pendingVerificationEmail ? (
              <button
                type="button"
                className="pixel-button secondary"
                disabled={loading}
                onClick={() => onResendVerification(pendingVerificationEmail)}
              >
                Resend verification email
              </button>
            ) : null}
            <button className="pixel-button" type="submit" disabled={loading}>
              {loading
                ? 'Loading...'
                : activeMode === 'login'
                  ? 'Enter Studio'
                  : activeMode === 'register'
                    ? 'Create Account'
                    : activeMode === 'forgot'
                      ? 'Send Reset Link'
                      : 'Reset Password'}
            </button>
            {activeMode === 'login' ? (
              <button
                type="button"
                className="text-xs text-[var(--accent)] hover:underline"
                onClick={() => selectMode('forgot')}
              >
                Forgot password?
              </button>
            ) : null}
            {activeMode === 'forgot' ? (
              <button
                type="button"
                className="text-xs text-[var(--accent)] hover:underline"
                onClick={() => selectMode('login')}
              >
                Back to login
              </button>
            ) : null}
          </form>
        </div>
      </div>
    </div>
  )
}
