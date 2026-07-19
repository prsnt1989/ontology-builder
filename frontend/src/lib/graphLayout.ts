import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

// Card dimensions — must match ObjectTypeNode's rendered size for good spacing.
export const NODE_WIDTH = 220
export const NODE_HEIGHT = 96

/**
 * Deterministic left-to-right hierarchical layout via Dagre.
 * Returns nodes with computed absolute {x, y} positions (top-left origin,
 * which is what React Flow expects).
 */
export function layoutGraph(nodes: Node[], edges: Edge[], direction: 'LR' | 'TB' = 'LR'): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: direction, nodesep: 48, ranksep: 96, marginx: 24, marginy: 24 })

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }))
  edges.forEach((e) => g.setEdge(e.source, e.target))

  dagre.layout(g)

  return nodes.map((n) => {
    const pos = g.node(n.id)
    return {
      ...n,
      // Dagre gives center coords; React Flow wants top-left.
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      sourcePosition: (direction === 'LR' ? 'right' : 'bottom') as Node['sourcePosition'],
      targetPosition: (direction === 'LR' ? 'left' : 'top') as Node['targetPosition'],
    }
  })
}
