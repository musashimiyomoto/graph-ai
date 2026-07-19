import { describe, expect, it } from 'vitest'

import {
  switchOutputHandles,
  validateSwitchBranches,
} from './switchBranches'

describe('Switch branches', () => {
  it('derives named handles followed by default', () => {
    expect(
      switchOutputHandles([
        { name: 'billing', value: 'billing' },
        { name: 'support', value: 'support' },
      ]),
    ).toEqual(['billing', 'support', 'default'])
  })

  it('rejects duplicate and reserved names', () => {
    expect(
      validateSwitchBranches([
        { name: 'same', value: 'one' },
        { name: 'same', value: 'two' },
      ]),
    ).toContain('duplicated')
    expect(
      validateSwitchBranches([{ name: 'default', value: 'fallback' }]),
    ).toContain('reserved')
  })

  it('requires stable names and non-empty values', () => {
    expect(
      validateSwitchBranches([{ name: 'Bad Name', value: 'value' }]),
    ).toContain('lowercase')
    expect(
      validateSwitchBranches([{ name: 'valid', value: ' ' }]),
    ).toContain('match value')
  })
})
