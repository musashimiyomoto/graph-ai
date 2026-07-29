import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useWorkflowTemplates } from '../hooks/useWorkflowTemplates'
import type { WorkflowTemplate } from '../lib/types'
import { NewFromTemplateDialog } from './NewFromTemplateDialog'

vi.mock('../hooks/useWorkflowTemplates')

const TEMPLATES: WorkflowTemplate[] = [
  {
    key: 'simple-chatbot',
    name: 'Simple Chatbot',
    description: 'A minimal LLM chat flow.',
    category: 'AI & Text',
    setup_steps: ['Choose an LLM provider and model.'],
    node_count: 3,
  },
  {
    key: 'email-auto-responder',
    name: 'Email Auto-Responder',
    description: 'Draft and send email replies.',
    category: 'Channels',
    setup_steps: ['Choose an email account.'],
    node_count: 3,
  },
  {
    key: 'text-compactor',
    name: 'Text Compactor',
    description: 'Shorten a long text without an LLM.',
    category: 'AI & Text',
    setup_steps: [],
    node_count: 7,
  },
]

describe('NewFromTemplateDialog', () => {
  beforeEach(() => {
    vi.mocked(useWorkflowTemplates).mockReturnValue({
      templates: TEMPLATES,
      loading: false,
    })
  })

  it('filters by category and creates the selected template with a custom name', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn().mockResolvedValue(undefined)

    render(<NewFromTemplateDialog onCancel={vi.fn()} onConfirm={onConfirm} />)

    await user.click(screen.getByRole('button', { name: 'Channels' }))
    expect(screen.queryByRole('button', { name: /Simple Chatbot/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Email Auto-Responder/ })).toBeInTheDocument()

    const nameInput = screen.getByLabelText('Workflow name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Support Inbox')
    await user.click(screen.getByRole('button', { name: 'Create workflow' }))

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith('email-auto-responder', 'Support Inbox')
    })
  })

  it('searches setup metadata and identifies templates ready to run', async () => {
    const user = userEvent.setup()

    render(<NewFromTemplateDialog onCancel={vi.fn()} onConfirm={vi.fn()} />)

    await user.type(screen.getByLabelText('Search templates'), 'without an llm')
    expect(screen.getByRole('button', { name: /Text Compactor/ })).toBeInTheDocument()
    expect(screen.getByText('Ready to run — no connections required.')).toBeInTheDocument()
  })
})
