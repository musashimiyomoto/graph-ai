import { describe, expect, it } from 'vitest'
import type { Edge, Node as FlowNode } from 'reactflow'

import { computeAutoLayout } from './autoLayout'

function makeNode(
  id: string,
  x: number,
  y: number,
  width?: number,
  height?: number,
): FlowNode {
  return {
    id,
    position: { x, y },
    data: {},
    width,
    height,
  } as FlowNode
}

describe('computeAutoLayout', () => {
  it('returns an empty map for no nodes', () => {
    expect(computeAutoLayout([], []).size).toBe(0)
  })

  it('positions every node', () => {
    const nodes = [
      makeNode('a', 0, 0, 180, 64),
      makeNode('b', 500, 0, 180, 64),
    ]
    const edges: Edge[] = [{ id: 'e', source: 'a', target: 'b' }]

    const layout = computeAutoLayout(nodes, edges)

    expect(layout.has('a')).toBe(true)
    expect(layout.has('b')).toBe(true)
  })

  it('lays a chain out left-to-right', () => {
    const nodes = [
      makeNode('a', 0, 0, 180, 64),
      makeNode('b', 0, 0, 180, 64),
    ]
    const edges: Edge[] = [{ id: 'e', source: 'a', target: 'b' }]

    const layout = computeAutoLayout(nodes, edges)

    const a = layout.get('a')!
    const b = layout.get('b')!
    // rankdir LR: the downstream node sits to the right of its parent.
    expect(b.x).toBeGreaterThan(a.x)
  })

  it('preserves the graph centre so the layout does not jump off-screen', () => {
    const nodes = [
      makeNode('a', 1000, 1000, 180, 64),
      makeNode('b', 1400, 1000, 180, 64),
    ]
    const edges: Edge[] = [{ id: 'e', source: 'a', target: 'b' }]

    const oldCenterX =
      nodes.reduce((sum, n) => sum + n.position.x + 90, 0) / nodes.length
    const oldCenterY =
      nodes.reduce((sum, n) => sum + n.position.y + 32, 0) / nodes.length

    const layout = computeAutoLayout(nodes, edges)

    const newCenterX =
      nodes.reduce((sum, n) => sum + (layout.get(n.id)!.x + 90), 0) /
      nodes.length
    const newCenterY =
      nodes.reduce((sum, n) => sum + (layout.get(n.id)!.y + 32), 0) /
      nodes.length

    expect(newCenterX).toBeCloseTo(oldCenterX, 5)
    expect(newCenterY).toBeCloseTo(oldCenterY, 5)
  })

  it('uses fallback sizes for unmeasured nodes without crashing', () => {
    const nodes = [makeNode('a', 0, 0), makeNode('b', 0, 0)]
    const edges: Edge[] = [{ id: 'e', source: 'a', target: 'b' }]

    const layout = computeAutoLayout(nodes, edges)

    expect(layout.size).toBe(2)
    expect(Number.isFinite(layout.get('a')!.x)).toBe(true)
  })
})
