import { describe, expect, it } from 'vitest'
import { fmtDate, humanize, isPast, relative } from './format'

describe('fmtDate', () => {
  it('returns em-dash for null/undefined', () => {
    expect(fmtDate(null)).toBe('—')
    expect(fmtDate(undefined)).toBe('—')
  })

  it('returns original string for invalid date', () => {
    expect(fmtDate('not-a-date')).toBe('not-a-date')
  })

  it('omits time for date-only values', () => {
    const result = fmtDate('2025-06-15')
    expect(result).not.toContain(':')
  })
})

describe('relative', () => {
  it('returns empty string for null/undefined', () => {
    expect(relative(null)).toBe('')
    expect(relative(undefined)).toBe('')
  })

  it('uses minutes for short durations', () => {
    const soon = new Date(Date.now() + 5 * 60_000).toISOString()
    expect(relative(soon)).toMatch(/^in \d+min$/)
  })

  it('uses hours for medium durations', () => {
    const later = new Date(Date.now() + 3 * 3_600_000).toISOString()
    expect(relative(later)).toMatch(/^in \d+h$/)
  })

  it('formats past dates with ago suffix', () => {
    const past = new Date(Date.now() - 2 * 86_400_000).toISOString()
    expect(relative(past)).toMatch(/\d+d ago$/)
  })
})

describe('humanize', () => {
  it('replaces underscores with spaces', () => {
    expect(humanize('action_required')).toBe('action required')
  })

  it('leaves already-spaced strings unchanged', () => {
    expect(humanize('urgent')).toBe('urgent')
  })
})

describe('isPast', () => {
  it('returns false for null/undefined', () => {
    expect(isPast(null)).toBe(false)
    expect(isPast(undefined)).toBe(false)
  })

  it('returns true for past dates', () => {
    expect(isPast(new Date(Date.now() - 10_000).toISOString())).toBe(true)
  })

  it('returns false for future dates', () => {
    expect(isPast(new Date(Date.now() + 10_000).toISOString())).toBe(false)
  })
})
