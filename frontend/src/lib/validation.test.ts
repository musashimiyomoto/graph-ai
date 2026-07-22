import { describe, expect, it } from 'vitest'

import type {
  NodeCatalogField,
  NodeCatalogFieldVisibility,
  NodeFieldValidator,
  NodeFieldWidget,
} from './types'
import { matchesVisibility, validateFields } from './validation'

function makeField(
  overrides: {
    name?: string
    required?: boolean
    widget?: NodeFieldWidget
    label?: string
    validators?: NodeFieldValidator
    visibleWhen?: NodeCatalogFieldVisibility | null
  } = {},
): NodeCatalogField {
  return {
    name: overrides.name ?? 'field',
    required: overrides.required ?? false,
    validators: overrides.validators ?? {},
    ui: {
      widget: overrides.widget ?? 'text',
      label: overrides.label ?? 'Field',
      placeholder: null,
      help: null,
      step: null,
      options: {},
    },
    default: undefined,
    datasource: null,
    visible_when: overrides.visibleWhen ?? null,
  }
}

function visibility(
  overrides: Partial<NodeCatalogFieldVisibility>,
): NodeCatalogFieldVisibility {
  return { field: 'other', equals: undefined, not_equals: undefined, ...overrides }
}

describe('matchesVisibility', () => {
  it('matches on equals when equals is set', () => {
    const rule = visibility({ equals: 'telegram' })
    expect(matchesVisibility(rule, 'telegram')).toBe(true)
    expect(matchesVisibility(rule, 'txt')).toBe(false)
  })

  it('treats a null equals as unset and falls through to not_equals', () => {
    // equals=null must NOT match a null controlling value; not_equals governs.
    const rule = visibility({ equals: null, not_equals: 'txt' })
    expect(matchesVisibility(rule, 'txt')).toBe(false)
    expect(matchesVisibility(rule, 'telegram')).toBe(true)
  })

  it('matches on not_equals when equals is unset', () => {
    const rule = visibility({ not_equals: 'schedule' })
    expect(matchesVisibility(rule, 'schedule')).toBe(false)
    expect(matchesVisibility(rule, 'txt')).toBe(true)
  })
})

describe('validateFields', () => {
  it('returns no errors for a valid required text field', () => {
    const fields = [makeField({ name: 'label', required: true })]
    expect(validateFields(fields, { label: 'hello' })).toEqual({})
  })

  it('flags an empty required text field', () => {
    const fields = [makeField({ name: 'label', required: true, label: 'Label' })]
    expect(validateFields(fields, { label: '   ' })).toEqual({
      label: 'Label is required',
    })
  })

  it('skips value validation for an optional empty field', () => {
    const fields = [
      makeField({
        name: 'sys',
        required: false,
        validators: { min_length: 5 },
      }),
    ]
    expect(validateFields(fields, { sys: '' })).toEqual({})
  })

  it('requires a real number for a required number widget', () => {
    const fields = [
      makeField({
        name: 'temp',
        required: true,
        widget: 'number',
        label: 'Temperature',
      }),
    ]
    // A cleared number field arriving as '' must fail, not coerce to 0.
    expect(validateFields(fields, { temp: '' })).toEqual({
      temp: 'Temperature is required',
    })
    expect(validateFields(fields, { temp: 0.5 })).toEqual({})
  })

  it('requires a positive provider id for a provider widget', () => {
    const fields = [
      makeField({
        name: 'llm_provider_id',
        required: true,
        widget: 'provider',
        label: 'Provider',
      }),
    ]
    expect(validateFields(fields, { llm_provider_id: 0 })).toEqual({
      llm_provider_id: 'Provider is required',
    })
    expect(validateFields(fields, { llm_provider_id: 3 })).toEqual({})
  })

  it('enforces min_length', () => {
    const fields = [
      makeField({
        name: 'name',
        required: true,
        label: 'Name',
        validators: { min_length: 3 },
      }),
    ]
    expect(validateFields(fields, { name: 'ab' })).toEqual({
      name: 'Name must be at least 3 character(s)',
    })
  })

  it('enforces ge and le bounds', () => {
    const fields = [
      makeField({
        name: 'top_p',
        required: true,
        widget: 'number',
        label: 'Top P',
        validators: { ge: 0, le: 1 },
      }),
    ]
    expect(validateFields(fields, { top_p: -0.5 })).toEqual({
      top_p: 'Top P must be ≥ 0',
    })
    expect(validateFields(fields, { top_p: 1.5 })).toEqual({
      top_p: 'Top P must be ≤ 1',
    })
    expect(validateFields(fields, { top_p: 0.5 })).toEqual({})
  })

  it('enforces select membership', () => {
    const fields = [
      makeField({
        name: 'format',
        required: true,
        widget: 'select',
        label: 'Format',
        validators: { select: ['txt', 'telegram'] },
      }),
    ]
    expect(validateFields(fields, { format: 'invalid' })).toEqual({
      format: 'Format has an invalid option',
    })
    expect(validateFields(fields, { format: 'telegram' })).toEqual({})
  })

  it('only requires a conditionally visible field while it is visible', () => {
    const fields = [
      makeField({
        name: 'webhook_url',
        required: true,
        label: 'Callback URL',
        visibleWhen: visibility({ equals: 'webhook' }),
      }),
    ]
    expect(validateFields(fields, { other: 'txt' })).toEqual({})
    expect(validateFields(fields, { other: 'webhook', webhook_url: '' })).toEqual({
      webhook_url: 'Callback URL is required',
    })
  })

  it('requires an absolute HTTP(S) URL', () => {
    const fields = [
      makeField({
        name: 'webhook_url',
        required: true,
        label: 'Callback URL',
        validators: { url: true },
      }),
    ]
    expect(validateFields(fields, { webhook_url: '/relative' })).toEqual({
      webhook_url: 'Callback URL must be an absolute HTTP(S) URL',
    })
    expect(validateFields(fields, { webhook_url: 'https://example.com/callback' })).toEqual({})
  })

  it('requires an ISO date/time with an explicit timezone', () => {
    const fields = [
      makeField({
        name: 'timestamp',
        required: true,
        label: 'Wait until',
        validators: { datetime: true },
      }),
    ]
    expect(validateFields(fields, { timestamp: '2026-07-21T09:00:00' })).toEqual({
      timestamp: 'Wait until must be an ISO 8601 date/time with timezone',
    })
    expect(
      validateFields(fields, { timestamp: '2026-07-21T09:00:00+03:00' }),
    ).toEqual({})
  })

  it('collects errors across multiple fields', () => {
    const fields = [
      makeField({ name: 'a', required: true, label: 'A' }),
      makeField({
        name: 'b',
        required: true,
        widget: 'number',
        label: 'B',
      }),
    ]
    expect(validateFields(fields, { a: '', b: 'x' })).toEqual({
      a: 'A is required',
      b: 'B is required',
    })
  })
})
