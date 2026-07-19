import {
  MAX_SWITCH_BRANCHES,
  readSwitchBranches,
  type SwitchBranch,
} from '../lib/switchBranches'

interface SwitchBranchesFieldProps {
  value: unknown
  onChange: (value: SwitchBranch[]) => void
}

export function SwitchBranchesField({ value, onChange }: SwitchBranchesFieldProps) {
  const branches = readSwitchBranches(value)

  function updateBranch(index: number, patch: Partial<SwitchBranch>) {
    onChange(
      branches.map((branch, branchIndex) =>
        branchIndex === index ? { ...branch, ...patch } : branch,
      ),
    )
  }

  function removeBranch(index: number) {
    if (branches.length <= 1) {
      return
    }
    onChange(branches.filter((_, branchIndex) => branchIndex !== index))
  }

  function addBranch() {
    if (branches.length >= MAX_SWITCH_BRANCHES) {
      return
    }
    const usedNames = new Set(branches.map((branch) => branch.name))
    let suffix = branches.length + 1
    while (usedNames.has(`branch_${suffix}`)) {
      suffix += 1
    }
    onChange([...branches, { name: `branch_${suffix}`, value: '' }])
  }

  return (
    <div className="flex flex-col gap-2">
      {branches.map((branch, index) => (
        <div
          key={index}
          className="grid grid-cols-[1fr_1fr_auto] items-center gap-2"
        >
          <input
            className="pixel-input min-w-0"
            aria-label={`Branch ${index + 1} name`}
            value={branch.name}
            placeholder="branch_name"
            onChange={(event) => updateBranch(index, { name: event.target.value })}
          />
          <input
            className="pixel-input min-w-0"
            aria-label={`Branch ${index + 1} match value`}
            value={branch.value}
            placeholder="Exact value"
            onChange={(event) => updateBranch(index, { value: event.target.value })}
          />
          <button
            type="button"
            className="pixel-button danger px-2"
            aria-label={`Remove branch ${index + 1}`}
            disabled={branches.length <= 1}
            onClick={() => removeBranch(index)}
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        className="pixel-button ghost"
        disabled={branches.length >= MAX_SWITCH_BRANCHES}
        onClick={addBranch}
      >
        + Add branch
      </button>
      <span className="text-xs text-[var(--muted)]">
        Unmatched values use the default output.
      </span>
    </div>
  )
}
