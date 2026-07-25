import { describe, expect, it } from 'vitest'

import {
  coercionLabel,
  portForHandle,
  requiredPortCoercion,
  resolvePortType,
} from './ports'

const ports = [
  {
    name: 'body',
    label: 'Body',
    type: 'text' as const,
    required: true,
    type_field: null,
    allowed_types: [],
  },
  {
    name: 'status',
    label: 'Status',
    type: 'json' as const,
    required: true,
    type_field: null,
    allowed_types: [],
  },
]

describe('typed ports', () => {
  it('resolves a dynamic port from node configuration', () => {
    expect(
      resolvePortType(
        {
          name: 'output',
          label: 'Output',
          type: 'text',
          required: true,
          type_field: 'output_type',
          allowed_types: ['text', 'json', 'list'],
        },
        { output_type: 'list' },
      ),
    ).toBe('list')
  })

  it('rejects configuration outside the current dynamic port contract', () => {
    expect(
      resolvePortType(
        {
          name: 'input',
          label: 'Input',
          type: 'text',
          required: true,
          type_field: 'input_type',
          allowed_types: ['text', 'json'],
        },
        { input_type: 'video' },
      ),
    ).toBeNull()
  })

  it('requires a concrete conversion only for convertible mismatches', () => {
    expect(requiredPortCoercion('text', 'text')).toBeNull()
    expect(requiredPortCoercion('text', 'json')).toBe('text_to_json')
    expect(requiredPortCoercion('file', 'text')).toBeUndefined()
    expect(coercionLabel('json_to_list')).toBe('json → list')
  })

  it('resolves default, named, and routing handles', () => {
    expect(portForHandle(ports, null)?.name).toBe('body')
    expect(portForHandle(ports, 'status')?.name).toBe('status')
    expect(portForHandle(ports, 'branch', true)?.name).toBe('body')
    expect(portForHandle(ports, 'missing')).toBeUndefined()
  })
})
