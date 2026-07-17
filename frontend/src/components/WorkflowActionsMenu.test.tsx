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
        onDelete={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByTitle('Workflow actions'))
    fireEvent.click(screen.getByText('Copy webhook URL'))

    expect(await screen.findByText('Copied')).toBeInTheDocument()
    expect(onCopyWebhook).toHaveBeenCalledOnce()
  })
})
