import type { NodeCatalogField, NodeCatalogFieldVisibility } from './types'
import { validateSwitchBranches } from './switchBranches'

/**
 * Evaluate a field's declarative `visible_when` rule against its controlling
 * sibling field's current value. Exactly one of `equals`/`not_equals` is set
 * on the rule (enforced backend-side).
 */
export function matchesVisibility(
  rule: NodeCatalogFieldVisibility,
  controllingValue: unknown,
): boolean {
  if (rule.equals !== null && rule.equals !== undefined) {
    return controllingValue === rule.equals
  }
  return controllingValue !== rule.not_equals
}

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
  const { min_length: minLength, ge, le, select, url, datetime } = field.validators

  if (field.ui.widget === 'switch_branches') {
    return validateSwitchBranches(value)
  }

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

  if (url && typeof value === 'string') {
    try {
      const parsed = new URL(value)
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return `${label} must be an absolute HTTP(S) URL`
      }
    } catch {
      return `${label} must be an absolute HTTP(S) URL`
    }
  }

  if (datetime && typeof value === 'string') {
    const parsed = new Date(value)
    const hasTimezone = /(Z|[+-]\d{2}:\d{2})$/i.test(value.trim())
    if (Number.isNaN(parsed.getTime()) || !hasTimezone) {
      return `${label} must be an ISO 8601 date/time with timezone`
    }
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

    if (
      field.visible_when &&
      !matchesVisibility(field.visible_when, data[field.visible_when.field])
    ) {
      continue
    }

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
