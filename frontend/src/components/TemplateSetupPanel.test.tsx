import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { WorkflowTemplate } from '../lib/types'
import { TemplateSetupPanel } from './TemplateSetupPanel'

const TEMPLATE: WorkflowTemplate = {
  key: 'simple-chatbot',
  name: 'Simple Chatbot',
  description: 'A minimal chat flow.',
  category: 'AI & Text',
  setup_steps: [
    'Add an LLM provider in Settings -> LLM Providers.',
    'Select the Assistant node and choose its provider and model.',
  ],
  settings_sections: ['providers'],
  node_count: 3,
}

describe('TemplateSetupPanel', () => {
  it('keeps post-create setup actionable from the editor', async () => {
    const user = userEvent.setup()
    const onOpenSettings = vi.fn()
    const onDismiss = vi.fn()

    render(
      <TemplateSetupPanel
        template={TEMPLATE}
        onOpenSettings={onOpenSettings}
        onDismiss={onDismiss}
      />,
    )

    expect(screen.getByText(/Select the Assistant node/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Open LLM Providers' }))
    expect(onOpenSettings).toHaveBeenCalledWith('providers')

    await user.click(
      screen.getByRole('button', { name: 'Dismiss template setup guide' }),
    )
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})
