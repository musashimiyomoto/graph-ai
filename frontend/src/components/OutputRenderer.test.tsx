import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { OutputRenderer } from './OutputRenderer'

describe('OutputRenderer', () => {
  it('renders plain text for the text port type', () => {
    render(<OutputRenderer value="hello world" portType="text" />)
    expect(screen.getByText('hello world')).toBeInTheDocument()
  })

  it('pretty-prints valid JSON', () => {
    const { container } = render(
      <OutputRenderer value='{"a":1}' portType="json" />,
    )
    const pre = container.querySelector('pre')
    expect(pre).not.toBeNull()
    // JSON.stringify(_, null, 2) indents nested keys.
    expect(pre?.textContent).toContain('"a": 1')
  })

  it('degrades malformed JSON to plain text', () => {
    const { container } = render(
      <OutputRenderer value="{not json" portType="json" />,
    )
    expect(container.querySelector('pre')).toBeNull()
    expect(screen.getByText('{not json')).toBeInTheDocument()
  })

  it('falls back to plain text for an unknown/unsupported port type', () => {
    const { container } = render(
      <OutputRenderer value="just text" portType="file" />,
    )
    expect(container.querySelector('pre')).toBeNull()
    expect(screen.getByText('just text')).toBeInTheDocument()
  })

  it('falls back to plain text when no port type is given', () => {
    render(<OutputRenderer value="no port" />)
    expect(screen.getByText('no port')).toBeInTheDocument()
  })
})
