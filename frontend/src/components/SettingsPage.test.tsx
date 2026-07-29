import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useChannelCatalog } from '../hooks/useChannelCatalog'
import { SettingsPage } from './SettingsPage'

vi.mock('../hooks/useChannelCatalog')
vi.mock('./ConnectionSettings', () => ({
  ConnectionSettings: () => <div>Connection settings content</div>,
}))
vi.mock('./ProviderSettings', () => ({
  ProviderSettings: () => <div>Provider settings content</div>,
}))
vi.mock('./PostgresConnectionSettings', () => ({
  PostgresConnectionSettings: () => <div>PostgreSQL settings content</div>,
}))
vi.mock('./MCPServerSettings', () => ({
  MCPServerSettings: () => <div>MCP settings content</div>,
}))
vi.mock('./VectorCollectionSettings', () => ({
  VectorCollectionSettings: () => <div>Vector settings content</div>,
}))

describe('SettingsPage', () => {
  it('opens a section requested by template setup guidance', () => {
    vi.mocked(useChannelCatalog).mockReturnValue({
      channelCatalog: [],
      loading: false,
      sourceLabels: {},
    })

    render(<SettingsPage onError={vi.fn()} initialSectionId="providers" />)

    expect(screen.getByRole('heading', { name: 'LLM Providers' })).toBeInTheDocument()
    expect(screen.getByText('Provider settings content')).toBeInTheDocument()
  })
})
