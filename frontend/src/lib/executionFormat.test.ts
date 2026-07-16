import { describe, expect, it } from 'vitest'

import { formatDuration, formatTime } from './executionFormat'

describe('formatDuration', () => {
  it('returns null when there is no finish time', () => {
    expect(formatDuration('2026-01-01T00:00:00Z', null)).toBeNull()
  })

  it('returns null for an invalid timestamp', () => {
    expect(formatDuration('not-a-date', '2026-01-01T00:00:00Z')).toBeNull()
  })

  it('returns null when finish precedes start', () => {
    expect(
      formatDuration('2026-01-01T00:00:02Z', '2026-01-01T00:00:01Z'),
    ).toBeNull()
  })

  it('formats sub-second durations in milliseconds', () => {
    expect(
      formatDuration('2026-01-01T00:00:00.000Z', '2026-01-01T00:00:00.250Z'),
    ).toBe('250ms')
  })

  it('formats durations of a second or more in seconds', () => {
    expect(
      formatDuration('2026-01-01T00:00:00.000Z', '2026-01-01T00:00:02.500Z'),
    ).toBe('2.5s')
  })

  it('treats exactly 1000ms as seconds', () => {
    expect(
      formatDuration('2026-01-01T00:00:00.000Z', '2026-01-01T00:00:01.000Z'),
    ).toBe('1.0s')
  })
})

describe('formatTime', () => {
  it('returns an em dash for an invalid date', () => {
    expect(formatTime('not-a-date')).toBe('—')
  })

  it('returns a non-dash string for a valid date', () => {
    // Locale-dependent formatting; assert it produced something real.
    const result = formatTime('2026-01-15T12:30:00Z')
    expect(result).not.toBe('—')
    expect(result.length).toBeGreaterThan(0)
  })
})
