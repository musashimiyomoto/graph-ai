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
  return positions
}
