import dagre from '@dagrejs/dagre'
import type { Edge, Node as FlowNode } from 'reactflow'

// Fallback size for a node React Flow hasn't measured yet (width/height are
// only set once a node has actually rendered at least one frame).
const FALLBACK_WIDTH = 180
const FALLBACK_HEIGHT = 64

export interface LayoutPosition {
  x: number
  y: number
}

// Computes a left-to-right layered layout (matching the app's existing
// Input -> ... -> Output convention) via dagre. Returns each node's new
// top-left position — dagre itself works in node-center coordinates, so the
// node's own (measured or estimated) size is subtracted back out here.
export function computeAutoLayout(
  nodes: FlowNode[],
  edges: Edge[],
): Map<string, LayoutPosition> {
  const graph = new dagre.graphlib.Graph()
  graph.setDefaultEdgeLabel(() => ({}))
  graph.setGraph({ rankdir: 'LR', nodesep: 48, ranksep: 96 })

  for (const node of nodes) {
    graph.setNode(node.id, {
      width: node.width ?? FALLBACK_WIDTH,
      height: node.height ?? FALLBACK_HEIGHT,
    })
  }
  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target)
  }

  dagre.layout(graph)

  const positions = new Map<string, LayoutPosition>()
  for (const node of nodes) {
    const laidOut = graph.node(node.id)
    const width = node.width ?? FALLBACK_WIDTH
    const height = node.height ?? FALLBACK_HEIGHT
    positions.set(node.id, {
      x: laidOut.x - width / 2,
      y: laidOut.y - height / 2,
    })
  }

  // dagre always lays out starting near its own coordinate origin,
  // regardless of where the graph currently sits — left uncorrected, the
  // whole graph would jump to that origin and could land outside the
  // visible viewport. Shift every new position by the same offset so the
  // new layout's center lands exactly where the old graph's center was.
  const oldCenter = centerOf(
    nodes.map((node) => ({
      x: node.position.x + (node.width ?? FALLBACK_WIDTH) / 2,
      y: node.position.y + (node.height ?? FALLBACK_HEIGHT) / 2,
    })),
  )
  const newCenter = centerOf(
    nodes.map((node) => {
      const position = positions.get(node.id)
      const width = node.width ?? FALLBACK_WIDTH
      const height = node.height ?? FALLBACK_HEIGHT
      return { x: (position?.x ?? 0) + width / 2, y: (position?.y ?? 0) + height / 2 }
    }),
  )
  const offsetX = oldCenter.x - newCenter.x
  const offsetY = oldCenter.y - newCenter.y
  for (const [id, position] of positions) {
    positions.set(id, { x: position.x + offsetX, y: position.y + offsetY })
  }

  return positions
}

function centerOf(points: LayoutPosition[]): LayoutPosition {
  if (points.length === 0) {
    return { x: 0, y: 0 }
  }
  const sum = points.reduce(
    (acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }),
    { x: 0, y: 0 },
  )
  return { x: sum.x / points.length, y: sum.y / points.length }
}
