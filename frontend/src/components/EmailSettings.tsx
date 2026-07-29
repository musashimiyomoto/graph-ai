import { useState } from 'react'

import { useEmailAccounts } from '../hooks/useEmailAccounts'
import type { ApiError } from '../lib/types'

type SmtpSecurity = 'starttls' | 'tls' | 'none'

interface EmailSettingsProps {
  onError: (err: ApiError) => void
}

export function EmailSettings({ onError }: EmailSettingsProps) {
  const [name, setName] = useState('')
  const [emailAddress, setEmailAddress] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [imapHost, setImapHost] = useState('')
  const [imapPort, setImapPort] = useState(993)
  const [imapUseSsl, setImapUseSsl] = useState(true)
  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState(587)
  const [smtpSecurity, setSmtpSecurity] = useState<SmtpSecurity>('starttls')
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  const { accounts, loading, creating, createAccount, removeAccount } =
    useEmailAccounts({ onError })

  const complete = Boolean(
    name.trim() &&
    emailAddress.trim() &&
    username.trim() &&
    password &&
    imapHost.trim() &&
    smtpHost.trim(),
  )

  async function handleCreate(): Promise<void> {
    const created = await createAccount({
      name: name.trim(),
      email_address: emailAddress.trim(),
      username: username.trim(),
      password,
      imap_host: imapHost.trim(),
      imap_port: imapPort,
      imap_use_ssl: imapUseSsl,
      smtp_host: smtpHost.trim(),
      smtp_port: smtpPort,
      smtp_use_tls: smtpSecurity === 'starttls',
      smtp_use_ssl: smtpSecurity === 'tls',
    })
    if (created) {
      setName('')
      setEmailAddress('')
      setUsername('')
      setPassword('')
      setImapHost('')
      setSmtpHost('')
    }
  }

  async function handleDelete(accountId: number): Promise<void> {
    if (await removeAccount(accountId)) {
      setConfirmDeleteId(null)
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-3">
        {loading ? (
          <div className="text-xs text-[var(--muted)]">Loading accounts...</div>
        ) : accounts.length === 0 ? (
          <div className="text-xs text-[var(--muted)]">No email accounts yet.</div>
        ) : null}
        {accounts.map((account) => (
          <div key={account.id} className="pixel-card">
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm">{account.name}</div>
              <div className="truncate text-xs text-[var(--muted)]">
                {account.email_address} · {account.enabled ? 'enabled' : 'disabled'}
              </div>
            </div>
            {confirmDeleteId === account.id ? (
              <>
                <button
                  type="button"
                  className="pixel-icon danger"
                  title="Confirm delete"
                  onClick={() => void handleDelete(account.id)}
                >
                  ✓
                </button>
                <button
                  type="button"
                  className="pixel-icon"
                  title="Cancel"
                  onClick={() => setConfirmDeleteId(null)}
                >
                  ✕
                </button>
              </>
            ) : (
              <button
                type="button"
                className="pixel-icon danger"
                onClick={() => setConfirmDeleteId(account.id)}
              >
                Del
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 border-t border-white/10 pt-4">
        <div className="mb-3 text-xs uppercase tracking-widest text-[var(--muted)]">
          Add account
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <label className="pixel-label">
            Name
            <input
              className="pixel-input medium"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label className="pixel-label">
            Email address
            <input
              className="pixel-input medium"
              type="email"
              value={emailAddress}
              onChange={(e) => setEmailAddress(e.target.value)}
            />
          </label>
          <label className="pixel-label">
            Username
            <input
              className="pixel-input medium"
              value={username}
              autoComplete="username"
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
          <label className="pixel-label">
            Password
            <input
              className="pixel-input medium"
              type="password"
              value={password}
              autoComplete="new-password"
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label className="pixel-label">
            IMAP host
            <input
              className="pixel-input medium"
              value={imapHost}
              onChange={(e) => setImapHost(e.target.value)}
            />
          </label>
          <label className="pixel-label">
            IMAP port
            <input
              className="pixel-input compact"
              type="number"
              min={1}
              max={65535}
              value={imapPort}
              onChange={(e) => setImapPort(Number(e.target.value))}
            />
          </label>
          <label className="pixel-label">
            SMTP host
            <input
              className="pixel-input medium"
              value={smtpHost}
              onChange={(e) => setSmtpHost(e.target.value)}
            />
          </label>
          <label className="pixel-label">
            SMTP port
            <input
              className="pixel-input compact"
              type="number"
              min={1}
              max={65535}
              value={smtpPort}
              onChange={(e) => setSmtpPort(Number(e.target.value))}
            />
          </label>
          <label className="pixel-label">
            SMTP security
            <select
              className="pixel-input compact"
              value={smtpSecurity}
              onChange={(e) => setSmtpSecurity(e.target.value as SmtpSecurity)}
            >
              <option value="starttls">STARTTLS</option>
              <option value="tls">TLS</option>
              <option value="none">None</option>
            </select>
          </label>
          <label className="pixel-label justify-end">
            <span className="flex items-center gap-2 py-2">
              <input
                type="checkbox"
                checked={imapUseSsl}
                onChange={(e) => setImapUseSsl(e.target.checked)}
              />
              IMAP TLS
            </span>
          </label>
        </div>
        <button
          type="button"
          className="pixel-button small mt-3"
          disabled={creating || !complete}
          onClick={() => void handleCreate()}
        >
          {creating ? 'Saving...' : 'Add Account'}
        </button>
      </div>
    </div>
  )
}
