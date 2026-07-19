import type { NodeCatalogItem, NodeType } from '../lib/types'
import { NodeIcon } from './NodeIcons'

// Purely a display grouping for the node palette below — the backend catalog
// stays the source of truth for what a node type is and does. A type not
// listed here still shows up, under "Other", so a new node type is never
// silently dropped from the palette.
const NODE_CATEGORIES: { label: string; types: NodeType[] }[] = [
  { label: 'I/O', types: ['input', 'output'] },
  { label: 'AI', types: ['llm'] },
  { label: 'Data', types: ['table', 'web_search', 'http_request'] },
  {
    label: 'Logic',
    types: ['template', 'condition', 'switch', 'code_transform', 'loop'],
  },
  { label: 'Composition', types: ['call_workflow'] },
  { label: 'Loop', types: ['loop_input', 'loop_output'] },
  { label: 'RAG', types: ['vector_ingest', 'vector_search'] },
]

function groupNodeCatalog(
  nodeCatalog: NodeCatalogItem[],
): { label: string; nodes: NodeCatalogItem[] }[] {
  const remaining = new Map(nodeCatalog.map((node) => [node.type, node]))
  const groups = NODE_CATEGORIES.map((category) => {
    const nodes = category.types
      .map((type) => remaining.get(type))
      .filter((node): node is NodeCatalogItem => node !== undefined)
    for (const node of nodes) {
      remaining.delete(node.type)
    }
    return { label: category.label, nodes }
  }).filter((category) => category.nodes.length > 0)

  if (remaining.size > 0) {
    groups.push({ label: 'Other', nodes: [...remaining.values()] })
  }
  return groups
}

interface NodePaletteProps {
  nodeCatalog: NodeCatalogItem[]
  onAddNode: (type: NodeType) => void
}

// The draggable/clickable list of creatable node types — shared by the main
// WorkflowSidebar (top-level scope) and LoopBodyModal (a loop's body scope),
// each passing in an already scope-filtered catalog.
export function NodePalette({ nodeCatalog, onAddNode }: NodePaletteProps) {
  return (
    <div>
      <div className="pixel-section-title">Nodes</div>
      <div className="mt-3 flex flex-col gap-4">
        {groupNodeCatalog(nodeCatalog).map((category) => (
          <div key={category.label}>
            <div className="mb-2 text-xs uppercase tracking-wide text-[var(--muted)]">
              {category.label}
            </div>
            <div className="grid grid-cols-1 gap-2">
              {category.nodes.map((catalogNode) => (
                <button
                  key={catalogNode.type}
                  type="button"
                  className="pixel-button ghost flex items-center gap-2"
                  draggable
                  onDragStart={(event) => {
                    event.dataTransfer.setData(
                      'application/graphai-node-type',
                      catalogNode.type,
                    )
                    event.dataTransfer.effectAllowed = 'move'
                  }}
                  onClick={() => onAddNode(catalogNode.type)}
                >
                  <NodeIcon iconKey={catalogNode.icon_key} /> {catalogNode.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
