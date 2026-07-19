export interface SwitchBranch {
  name: string
  value: string
}

export const DEFAULT_SWITCH_HANDLE = 'default'
export const MAX_SWITCH_BRANCHES = 8
const BRANCH_NAME_PATTERN = /^[a-z][a-z0-9_-]{0,31}$/

export function readSwitchBranches(value: unknown): SwitchBranch[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.map((branch) => {
    if (!branch || typeof branch !== 'object') {
      return { name: '', value: '' }
    }
    const record = branch as Record<string, unknown>
    return {
      name: typeof record.name === 'string' ? record.name : '',
      value: typeof record.value === 'string' ? record.value : '',
    }
  })
}

export function validateSwitchBranches(value: unknown): string | null {
  const branches = readSwitchBranches(value)
  if (branches.length < 1 || branches.length > MAX_SWITCH_BRANCHES) {
    return `Branches must contain between 1 and ${MAX_SWITCH_BRANCHES} items`
  }

  const seen = new Set<string>()
  for (const [index, branch] of branches.entries()) {
    if (!BRANCH_NAME_PATTERN.test(branch.name)) {
      return `Branch ${index + 1} name must start with a lowercase letter and use only lowercase letters, numbers, _ or -`
    }
    if (branch.name === DEFAULT_SWITCH_HANDLE) {
      return `"${DEFAULT_SWITCH_HANDLE}" is reserved for unmatched values`
    }
    if (seen.has(branch.name)) {
      return `Branch name "${branch.name}" is duplicated`
    }
    if (branch.value.trim() === '') {
      return `Branch "${branch.name}" needs a match value`
    }
    seen.add(branch.name)
  }
  return null
}

export function switchOutputHandles(value: unknown): string[] {
  const branches = readSwitchBranches(value)
  const names = branches
    .map((branch) => branch.name)
    .filter(
      (name, index) =>
        BRANCH_NAME_PATTERN.test(name) &&
        name !== DEFAULT_SWITCH_HANDLE &&
        branches.findIndex((branch) => branch.name === name) === index,
    )
  return [...names, DEFAULT_SWITCH_HANDLE]
}
