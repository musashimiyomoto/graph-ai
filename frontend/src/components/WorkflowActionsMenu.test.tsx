import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { WorkflowActionsMenu } from './WorkflowActionsMenu'

describe('WorkflowActionsMenu', () => {
  it('confirms when the webhook URL has been copied', async () => {
    const onCopyWebhook = vi.fn().mockResolvedValue(true)
    render(
      <WorkflowActionsMenu
        onEdit={vi.fn()}
        onDuplicate={vi.fn()}
        onExport={vi.fn()}
        onCopyWebhook={onCopyWebhook}
        onCopyWebChat={vi.fn().mockResolvedValue(true)}
        onDelete={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByTitle('Workflow actions'))
    fireEvent.click(screen.getByText('Copy webhook URL'))

    expect(await screen.findByText('Copied')).toBeInTheDocument()
    expect(onCopyWebhook).toHaveBeenCalledOnce()
  })

  it('confirms when the web-chat embed has been copied', async () => {
    const onCopyWebChat = vi.fn().mockResolvedValue(true)
    render(
      <WorkflowActionsMenu
        onEdit={vi.fn()}
        onDuplicate={vi.fn()}
        onExport={vi.fn()}
        onCopyWebhook={vi.fn().mockResolvedValue(true)}
        onCopyWebChat={onCopyWebChat}
        onDelete={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByTitle('Workflow actions'))
    fireEvent.click(screen.getByText('Copy web chat embed'))

    expect(await screen.findByText('Copied')).toBeInTheDocument()
    expect(onCopyWebChat).toHaveBeenCalledOnce()
  })
})
