import { useState } from 'react'

import type { ApiError } from '../lib/types'
import { useTelegramBots } from '../hooks/useTelegramBots'

interface TelegramSettingsProps {
  onError: (err: ApiError) => void
}

export function TelegramSettings({ onError }: TelegramSettingsProps) {
  const [name, setName] = useState('')
  const [botToken, setBotToken] = useState('')
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  const { bots, loading, creating, createBot, removeBot } = useTelegramBots({ onError })

  async function handleCreate(): Promise<void> {
    try {
      const created = await createBot({
        name: name.trim(),
        bot_token: botToken.trim(),
      })
      if (created) {
        setName('')
        setBotToken('')
      }
    } catch (error) {
      onError(error as ApiError)
    }
  }

  async function handleDelete(botId: number): Promise<void> {
    await removeBot(botId)
    setConfirmDeleteId(null)
  }

  return (
    <div>
      <div className="flex flex-col gap-3">
        {loading ? (
          <div className="text-xs text-[var(--muted)]">Loading bots...</div>
        ) : bots.length === 0 ? (
          <div className="text-xs text-[var(--muted)]">
            No bots yet.
          </div>
        ) : null}
        {bots.map((bot) => (
          <div key={bot.id} className="pixel-card">
            <div className="flex-1">
              <div className="text-sm">{bot.name}</div>
              <div className="text-xs text-[var(--muted)]">
                {bot.enabled ? 'enabled' : 'disabled'}
              </div>
            </div>
            {confirmDeleteId === bot.id ? (
              <>
                <button
                  type="button"
                  className="pixel-icon danger"
                  title="Confirm delete"
                  onClick={() => void handleDelete(bot.id)}
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
                onClick={() => setConfirmDeleteId(bot.id)}
              >
                Del
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 border-t border-white/10 pt-4">
        <div className="mb-3 text-xs uppercase tracking-widest text-[var(--muted)]">
          Add bot
        </div>
        <div className="pixel-form-stack">
          <label className="pixel-label">
            Name
            <input
              className="pixel-input medium"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Bot"
            />
          </label>
          <label className="pixel-label">
            Bot Token
            <input
              className="pixel-input"
              type="password"
              value={botToken}
              autoComplete="off"
              onChange={(e) => setBotToken(e.target.value)}
              placeholder="123456:ABC-DEF..."
            />
          </label>
          <button
            type="button"
            className="pixel-button small"
            disabled={creating || !name.trim() || !botToken.trim()}
            onClick={() => void handleCreate()}
          >
            {creating ? 'Saving...' : 'Add Bot'}
          </button>
        </div>
      </div>
    </div>
  )
}
