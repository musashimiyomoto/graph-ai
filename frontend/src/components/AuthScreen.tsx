import type { FormEvent } from 'react'
import { useState } from 'react'

interface AuthScreenProps {
  loading: boolean
  error: string | null
  onLogin: (email: string, password: string) => void
  onRegister: (email: string, password: string) => void
}

export function AuthScreen({
  loading,
  error,
  onLogin,
  onRegister,
}: AuthScreenProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (mode === 'login') {
      onLogin(email.trim(), password)
    } else {
      onRegister(email.trim(), password)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <div className="mx-auto flex min-h-screen w-full max-w-4xl flex-col items-center justify-center gap-8 px-6 py-12">
        <div className="flex flex-col items-center gap-3 text-center">
          <span className="text-xs uppercase tracking-[0.2em] text-[var(--accent)]">
            Graph AI
          </span>
          <h1 className="font-pixel text-3xl uppercase">
            Pixel Flow Studio
          </h1>
          <p className="text-base text-[var(--muted)]">
            Минималистичный редактор для workflows с n8n vibe.
          </p>
        </div>

        <div className="pixel-panel w-full max-w-md">
          <div className="flex gap-2">
            <button
              type="button"
              className={`pixel-tab ${mode === 'login' ? 'is-active' : ''}`}
              onClick={() => setMode('login')}
            >
              Login
            </button>
            <button
              type="button"
              className={`pixel-tab ${mode === 'register' ? 'is-active' : ''}`}
              onClick={() => setMode('register')}
            >
              Register
            </button>
          </div>
          <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit}>
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
            <label className="pixel-label">
              Password
              <input
                className="pixel-input"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                required
              />
            </label>
            {error ? <div className="pixel-error">{error}</div> : null}
            <button className="pixel-button" type="submit" disabled={loading}>
              {loading
                ? 'Loading...'
                : mode === 'login'
                  ? 'Enter Studio'
                  : 'Create Account'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
