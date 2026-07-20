import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { WidgetApp } from './WidgetApp'
import {
  createWebChatExecution,
  getWebChatExecution,
  streamWebChatExecution,
} from './api'

vi.mock('./api', () => ({
  createWebChatExecution: vi.fn(),
  getWebChatExecution: vi.fn(),
  streamWebChatExecution: vi.fn(),
}))

const createMock = vi.mocked(createWebChatExecution)
const getMock = vi.mocked(getWebChatExecution)
const streamMock = vi.mocked(streamWebChatExecution)

describe('WidgetApp', () => {
  beforeEach(() => {
    createMock.mockReset()
    getMock.mockReset()
    streamMock.mockReset()
  })

  it('sends a visitor message and renders the streamed final response', async () => {
    const created = {
      id: 4,
      workflow_id: 2,
      version_id: 1,
      status: 'created' as const,
      source: 'web_chat' as const,
      input_data: { value: 'Hello' },
      output_data: null,
      error: null,
      approval_node_id: null,
      approval_prompt: null,
      approval_input: null,
      queue_job_id: null,
      wait_until: null,
      prefect_flow_run_id: null,
      started_at: '2026-07-18T00:00:00Z',
      finished_at: null,
    }
    const finished = {
      ...created,
      status: 'success' as const,
      output_data: { value: 'Welcome!' },
      finished_at: '2026-07-18T00:00:01Z',
    }
    createMock.mockResolvedValue(created)
    streamMock.mockImplementation(async (_endpoint, _id, onEvent) => {
      onEvent({ type: 'status', execution: finished })
    })

    render(<WidgetApp endpoint="https://graph.example/api/web-chat/token" title="Support" />)
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Hello' } })
    fireEvent.click(screen.getByText('Send'))

    expect(await screen.findByText('Welcome!')).toBeInTheDocument()
    expect(createMock).toHaveBeenCalledWith(
      'https://graph.example/api/web-chat/token',
      'Hello',
    )
    expect(getMock).not.toHaveBeenCalled()
  })
})
