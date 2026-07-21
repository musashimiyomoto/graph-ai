import { describe, expect, it } from 'vitest'

import { coercionLabel, requiredPortCoercion, resolvePortType } from './ports'

describe('typed ports', () => {
  it('resolves a dynamic port from node configuration', () => {
    expect(
      resolvePortType(
        {
          name: 'output',
          label: 'Output',
          type: 'text',
          type_field: 'output_type',
          allowed_types: ['text', 'json', 'list'],
        },
        { output_type: 'list' },
      ),
    ).toBe('list')
  })

  it('falls back to the declared type for stale configuration', () => {
    expect(
      resolvePortType(
        {
          name: 'input',
          label: 'Input',
          type: 'text',
          type_field: 'input_type',
          allowed_types: ['text', 'json'],
        },
        { input_type: 'video' },
      ),
    ).toBe('text')
  })

  it('requires a concrete conversion only for convertible mismatches', () => {
    expect(requiredPortCoercion('text', 'text')).toBeNull()
    expect(requiredPortCoercion('text', 'json')).toBe('text_to_json')
    expect(requiredPortCoercion('file', 'text')).toBeUndefined()
    expect(coercionLabel('json_to_list')).toBe('json → list')
  })
})
