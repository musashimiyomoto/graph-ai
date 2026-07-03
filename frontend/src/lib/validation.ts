import type { NodeCatalogField } from './types'

function isEmptyValue(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    (typeof value === 'string' && value.trim() === '')
  )
}

function requiredError(field: NodeCatalogField, value: unknown): string | null {
  const label = field.ui.label
  if (field.ui.widget === 'number') {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return `${label} is required`
    }
    return null
  }
  if (field.ui.widget === 'provider') {
    if (!Number.isInteger(Number(value)) || Number(value) <= 0) {
      return `${label} is required`
    }
    return null
  }
  return isEmptyValue(value) ? `${label} is required` : null
}

function valueError(field: NodeCatalogField, value: unknown): string | null {
  const label = field.ui.label
  const { min_length: minLength, ge, le, select } = field.validators

  if (minLength !== undefined && typeof value === 'string') {
    if (value.length < minLength) {
      return `${label} must be at least ${minLength} character(s)`
    }
  }

  if (typeof value === 'number' && !Number.isNaN(value)) {
    if (ge !== undefined && value < ge) {
      return `${label} must be ≥ ${ge}`
    }
    if (le !== undefined && value > le) {
      return `${label} must be ≤ ${le}`
    }
  }

  if (
    select &&
    select.length > 0 &&
    typeof value === 'string' &&
    value !== '' &&
    !select.includes(value)
  ) {
    return `${label} has an invalid option`
  }

  return null
}

/**
 * Validate node field values against the catalog schema.
 *
 * Enforces `required`, `min_length`, `ge`/`le`, and `select` membership so the
 * UI catches invalid config before it reaches the server. Optional fields that
 * are empty skip value validation.
 */
export function validateFields(
  fields: NodeCatalogField[],
  data: Record<string, unknown>,
): Record<string, string> {
  const errors: Record<string, string> = {}

  for (const field of fields) {
    const value = data[field.name]

    if (field.required) {
      const required = requiredError(field, value)
      if (required) {
        errors[field.name] = required
        continue
      }
    } else if (isEmptyValue(value)) {
      continue
    }

    const invalid = valueError(field, value)
    if (invalid) {
      errors[field.name] = invalid
    }
  }

  return errors
}
