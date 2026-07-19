import { describe, expect, it } from 'vitest'

import { ACTIVE_STATUSES } from './types'

describe('ACTIVE_STATUSES', () => {
  it('contains exactly the in-progress statuses', () => {
    expect(ACTIVE_STATUSES).toEqual([
      'created',
      'running',
      'waiting_approval',
    ])
  })
})
