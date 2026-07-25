import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import type { ApiError, Execution } from '../lib/types'
import {
  createWebChatExecution,
  getWebChatExecution,
  streamWebChatExecution,
} from './api'

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
  pending?: boolean
  failed?: boolean
}

interface WidgetAppProps {
  endpoint: string
  title: string
}

const POLL_INTERVAL_MS = 1_000
const MAX_POLL_ATTEMPTS = 300

function createPublicId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function sessionStorageKey(endpoint: string): string {
  return `graph-ai:web-chat:${endpoint}`
}

function readSession(endpoint: string): string | null {
  try {
    return window.sessionStorage.getItem(sessionStorageKey(endpoint))
  } catch {
    return null
  }
}

function storeSession(endpoint: string, sessionId: string): void {
  try {
    window.sessionStorage.setItem(sessionStorageKey(endpoint), sessionId)
  } catch {
    // A privacy-restricted embed can still keep the session for this mount.
  }
}

function finalText(execution: Execution): string {
  if (execution.status === 'cancelled') {
    return 'Execution cancelled.'
  }
  if (execution.status === 'rejected') {
    return 'Execution rejected.'
  }
  if (execution.status === 'failed') {
    return execution.error ?? 'The workflow failed.'
  }
  return String(execution.output_data?.value ?? '') || '(empty response)'
}

export function WidgetApp({ endpoint, title }: WidgetAppProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const nextId = useRef(1)
  const sessionId = useRef<string | null>(readSession(endpoint))
  const controller = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  let endpointAvailable = false
  try {
    const parsed = new URL(endpoint)
    endpointAvailable = parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    endpointAvailable = false
  }

  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  function updateAssistant(id: number, text: string, options: Partial<ChatMessage> = {}) {
    setMessages((previous) =>
      previous.map((message) =>
        message.id === id ? { ...message, text, ...options } : message,
      ),
    )
  }

  async function pollUntilFinished(
    executionId: number,
    publicSessionId: string,
  ): Promise<Execution> {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS))
      const execution = await getWebChatExecution(
        endpoint,
        executionId,
        publicSessionId,
      )
      if (
        execution.status === 'success' ||
        execution.status === 'failed' ||
        execution.status === 'cancelled' ||
        execution.status === 'rejected'
      ) {
        return execution
      }
    }
    throw { message: 'The response timed out.', status: 0 } as ApiError
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const value = draft.trim()
    if (!value || sending) return

    const userId = nextId.current++
    const assistantId = nextId.current++
    setMessages((previous) => [
      ...previous,
      { id: userId, role: 'user', text: value },
      { id: assistantId, role: 'assistant', text: '', pending: true },
    ])
    setDraft('')
    setSending(true)

    try {
      const execution = await createWebChatExecution(
        endpoint,
        value,
        createPublicId(),
        sessionId.current,
      )
      sessionId.current = execution.session_id
      storeSession(endpoint, execution.session_id)
      const tokenText = new Map<number, string>()
      let terminal: Execution | null = null
      const abortController = new AbortController()
      controller.current = abortController

      try {
        await streamWebChatExecution(
          endpoint,
          execution.id,
          execution.session_id,
          (streamEvent) => {
            if (streamEvent.type === 'token') {
              tokenText.set(
                streamEvent.node_id,
                (tokenText.get(streamEvent.node_id) ?? '') + streamEvent.delta,
              )
              updateAssistant(assistantId, [...tokenText.values()].join('\n'), {
                pending: true,
              })
              return
            }
            if (streamEvent.type === 'token_reset') {
              tokenText.set(streamEvent.node_id, '')
              return
            }
            if (
              streamEvent.type === 'status' &&
              (streamEvent.execution.status === 'success' ||
                streamEvent.execution.status === 'failed' ||
                streamEvent.execution.status === 'cancelled' ||
                streamEvent.execution.status === 'rejected')
            ) {
              terminal = streamEvent.execution
            }
          },
          abortController.signal,
        )
      } catch {
        // The status endpoint below is the source-of-truth fallback.
      }

      terminal ??= await pollUntilFinished(execution.id, execution.session_id)
      updateAssistant(assistantId, finalText(terminal), {
        pending: false,
        failed: terminal.status === 'failed',
      })
    } catch (error) {
      updateAssistant(assistantId, (error as ApiError).message ?? 'Request failed.', {
        pending: false,
        failed: true,
      })
    } finally {
      controller.current = null
      setSending(false)
    }
  }

  if (!endpointAvailable) {
    return <div className="widget-unavailable">Chat unavailable.</div>
  }

  return (
    <main className="widget-shell">
      <header className="widget-header">
        <div className="widget-status" />
        <strong>{title}</strong>
      </header>
      <div ref={scrollRef} className="widget-messages" aria-live="polite">
        {messages.length === 0 ? (
          <div className="widget-empty">How can I help?</div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`widget-message ${message.role} ${message.failed ? 'failed' : ''}`}
            >
              {message.pending && !message.text ? (
                <span className="widget-typing">...</span>
              ) : (
                message.text
              )}
            </div>
          ))
        )}
      </div>
      <form className="widget-form" onSubmit={(event) => void sendMessage(event)}>
        <input
          aria-label="Message"
          value={draft}
          placeholder="Type a message"
          maxLength={50_000}
          disabled={sending}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button type="submit" disabled={sending || !draft.trim()}>
          Send
        </button>
      </form>
    </main>
  )
}
