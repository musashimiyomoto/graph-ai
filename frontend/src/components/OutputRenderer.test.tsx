import userEvent from '@testing-library/user-event'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getArtifactDownload } from '../lib/api'
import { OutputRenderer } from './OutputRenderer'

vi.mock('../lib/api', () => ({
  getArtifactDownload: vi.fn(),
}))

const mockedGetArtifactDownload = vi.mocked(getArtifactDownload)

describe('OutputRenderer', () => {
  beforeEach(() => {
    mockedGetArtifactDownload.mockReset()
  })

  it('renders plain text for the text port type', () => {
    render(
      <OutputRenderer
        typedValue={{
          kind: 'text',
          value: 'hello world',
          artifact: null,
          metadata: {},
        }}
      />,
    )
    expect(screen.getByText('hello world')).toBeInTheDocument()
  })

  it('pretty-prints valid JSON', () => {
    const { container } = render(
      <OutputRenderer
        typedValue={{
          kind: 'json',
          value: { a: 1 },
          artifact: null,
          metadata: {},
        }}
      />,
    )
    const pre = container.querySelector('pre')
    expect(pre).not.toBeNull()
    // JSON.stringify(_, null, 2) indents nested keys.
    expect(pre?.textContent).toContain('"a": 1')
  })

  it('renders a structured typed value directly', () => {
    const { container } = render(
      <OutputRenderer
        typedValue={{
          kind: 'list',
          value: [1, { ok: true }],
          artifact: null,
          metadata: {},
        }}
      />,
    )
    expect(container.querySelector('pre')?.textContent).toContain('"ok": true')
  })

  it('resolves a signed URL before safely previewing an image artifact', async () => {
    const user = userEvent.setup()
    mockedGetArtifactDownload.mockResolvedValue({
      url: 'https://files.example.test/signed-image',
      expires_at: '2030-01-01T00:00:00Z',
    })
    render(
      <OutputRenderer
        typedValue={{
          kind: 'image',
          value: null,
          artifact: {
            artifact_id: 42,
            filename: 'chart.png',
            mime_type: 'image/png',
            size: 2048,
            checksum: 'a'.repeat(64),
          },
          metadata: {},
        }}
      />,
    )

    expect(screen.getByText('chart.png')).toBeInTheDocument()
    expect(screen.getByText('image/png · 2.0 KB')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Preview' }))

    expect(mockedGetArtifactDownload).toHaveBeenCalledWith(42)
    expect(await screen.findByRole('img', { name: 'chart.png' })).toHaveAttribute(
      'src',
      'https://files.example.test/signed-image',
    )
    expect(screen.queryByRole('iframe')).not.toBeInTheDocument()
  })

  it('offers download without embedding a generic file artifact', async () => {
    const user = userEvent.setup()
    mockedGetArtifactDownload.mockResolvedValue({
      url: 'https://files.example.test/signed-file',
      expires_at: '2030-01-01T00:00:00Z',
    })
    render(
      <OutputRenderer
        typedValue={{
          kind: 'file',
          value: null,
          artifact: {
            artifact_id: 7,
            filename: 'report.pdf',
            mime_type: 'application/pdf',
            size: 512,
            checksum: 'b'.repeat(64),
          },
          metadata: {},
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Get download' }))

    expect(await screen.findByRole('link', { name: 'Download' })).toHaveAttribute(
      'href',
      'https://files.example.test/signed-file',
    )
    expect(document.querySelector('iframe, embed, object')).toBeNull()
  })
})
