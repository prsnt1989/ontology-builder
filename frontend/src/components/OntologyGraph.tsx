import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Node,
  type Edge,
  type NodeMouseHandler,
  type EdgeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Loader2, Network, Maximize2, RefreshCw, GitPullRequestArrow, AlertTriangle } from 'lucide-react'
import { getOntologyGraph, type GraphObjectType, type GraphRelationship } from '../lib/api'
import { layoutGraph } from '../lib/graphLayout'
import { ObjectTypeNode, type ObjectTypeNodeData } from './ObjectTypeNode'
import { GraphDetailPanel, CARDINALITY_LABEL } from './GraphDetailPanel'
import { RequestChangesModal } from './RequestChangesModal'

interface Props {
  sessionId: string
  onRequestChanges?: (changes: string[]) => void
}

const nodeTypes = { objectType: ObjectTypeNode }

const CARD_MARK: Record<string, string> = {
  one_to_one: '1—1',
  one_to_many: '1—∗',
  many_to_one: '∗—1',
  many_to_many: '∗—∗',
}

function buildGraph(data: { object_types: GraphObjectType[]; relationships: GraphRelationship[] }) {
  const validIds = new Set(data.object_types.map((o) => o.api_name))

  const rawNodes: Node[] = data.object_types.map((ot) => ({
    id: ot.api_name,
    type: 'objectType',
    position: { x: 0, y: 0 },
    data: { objectType: ot },
  }))

  const validRels = data.relationships.filter(
    (r) => validIds.has(r.from_object_type) && validIds.has(r.to_object_type)
  )
  const droppedRels = data.relationships.length - validRels.length

  const rawEdges: Edge[] = validRels.map((r) => ({
    id: r.api_name || `${r.from_object_type}-${r.to_object_type}`,
    source: r.from_object_type,
    target: r.to_object_type,
    label: `${r.display_name}  ·  ${CARD_MARK[r.cardinality] ?? ''}`.trim(),
    labelShowBg: true,
    markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
    data: { relationship: r },
  }))

  // Mark isolated object types (no connected edge) so they're visible.
  const connected = new Set<string>()
  validRels.forEach((r) => {
    connected.add(r.from_object_type)
    connected.add(r.to_object_type)
  })
  const isolatedCount = rawNodes.filter((n) => !connected.has(n.id)).length
  rawNodes.forEach((n) => {
    ;(n.data as ObjectTypeNodeData & { isolated?: boolean }).isolated = !connected.has(n.id)
  })

  const laidOut = layoutGraph(rawNodes, rawEdges, 'LR')
  return { nodes: laidOut, edges: rawEdges, droppedRels, isolatedCount }
}

function GraphInner({ sessionId, onRequestChanges }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [data, setData] = useState<{ object_types: GraphObjectType[]; relationships: GraphRelationship[] } | null>(
    null
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphObjectType | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<GraphRelationship | null>(null)
  const [changesOpen, setChangesOpen] = useState(false)
  const [graphStats, setGraphStats] = useState<{ droppedRels: number; isolatedCount: number }>({
    droppedRels: 0,
    isolatedCount: 0,
  })
  const { fitView, setCenter, getNode } = useReactFlow()

  const relayout = useCallback(() => {
    if (!data) return
    const { nodes: n, edges: e, droppedRels, isolatedCount } = buildGraph(data)
    setNodes(n)
    setEdges(e)
    setGraphStats({ droppedRels, isolatedCount })
    window.setTimeout(() => fitView({ padding: 0.15, duration: 400 }), 50)
  }, [data, setNodes, setEdges, fitView])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setSelectedNode(null)
    setSelectedEdge(null)
    getOntologyGraph(sessionId)
      .then((d) => {
        if (cancelled) return
        setData(d)
        const { nodes: n, edges: e, droppedRels, isolatedCount } = buildGraph(d)
        setNodes(n)
        setEdges(e)
        setGraphStats({ droppedRels, isolatedCount })
        window.setTimeout(() => fitView({ padding: 0.15, duration: 300 }), 60)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load ontology graph')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [sessionId, setNodes, setEdges, fitView])

  const focusNode = useCallback(
    (apiName: string) => {
      const ot = data?.object_types.find((o) => o.api_name === apiName) ?? null
      setSelectedNode(ot)
      setSelectedEdge(null)
      const n = getNode(apiName)
      if (n) setCenter(n.position.x + 110, n.position.y + 48, { zoom: 1.1, duration: 400 })
      setNodes((nds) => nds.map((nd) => ({ ...nd, selected: nd.id === apiName })))
    },
    [data, getNode, setCenter, setNodes]
  )

  const onNodeClick: NodeMouseHandler = useCallback(
    (_evt, node) => {
      const ot = (node.data as { objectType: GraphObjectType }).objectType
      setSelectedNode(ot)
      setSelectedEdge(null)
    },
    []
  )

  const onEdgeClick: EdgeMouseHandler = useCallback((_evt, edge) => {
    const rel = (edge.data as { relationship: GraphRelationship } | undefined)?.relationship ?? null
    setSelectedEdge(rel)
    setSelectedNode(null)
  }, [])

  const closePanel = useCallback(() => {
    setSelectedNode(null)
    setSelectedEdge(null)
    setNodes((nds) => nds.map((nd) => ({ ...nd, selected: false })))
  }, [setNodes])

  const styledEdges = useMemo(
    () =>
      edges.map((e) => {
        const active =
          selectedEdge && (e.data as { relationship: GraphRelationship } | undefined)?.relationship?.api_name === selectedEdge.api_name
        return {
          ...e,
          animated: !!active,
          style: {
            stroke: active ? 'var(--primary)' : 'var(--border)',
            strokeWidth: active ? 2 : 1.5,
          },
          labelStyle: { fontSize: 11, fill: 'var(--muted-foreground)' },
          labelBgStyle: { fill: 'var(--card)', fillOpacity: 0.9 },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 4,
        }
      }),
    [edges, selectedEdge]
  )

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" />
        Loading ontology graph…
      </div>
    )
  }

  if (error || !data || data.object_types.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-muted-foreground">
        <Network className="size-8 opacity-40" />
        <div className="max-w-xs text-sm">
          {error === 'API error: 404' || !data
            ? 'No ontology to visualize yet. Finish designing the ontology, then come back to explore it as a graph.'
            : error}
        </div>
      </div>
    )
  }

  return (
    <div className="relative h-full">
      <ReactFlow
        nodes={nodes}
        edges={styledEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={closePanel}
        fitView
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} className="!bg-background" color="var(--border)" />
        <Controls className="!rounded-lg !border !border-border !bg-card !shadow-sm [&_button]:!border-border [&_button]:!bg-card [&_button]:!fill-foreground [&_button:hover]:!bg-muted" />
        <MiniMap
          pannable
          zoomable
          className="!rounded-lg !border !border-border !bg-card"
          maskColor="color-mix(in oklch, var(--muted) 60%, transparent)"
          nodeColor="var(--primary)"
        />
      </ReactFlow>

      {/* Toolbar */}
      <div className="absolute left-3 top-3 z-10 flex items-center gap-2 rounded-lg border border-border bg-card/90 px-2 py-1.5 shadow-sm backdrop-blur-sm">
        <span className="px-1 text-xs font-medium text-muted-foreground">
          {data.object_types.length} types · {edges.length} relationships
        </span>
        <button
          onClick={() => fitView({ padding: 0.15, duration: 400 })}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:bg-muted"
          title="Fit to view"
        >
          <Maximize2 className="size-3.5" />
          Fit
        </button>
        <button
          onClick={relayout}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:bg-muted"
          title="Re-layout"
        >
          <RefreshCw className="size-3.5" />
          Re-layout
        </button>
        {onRequestChanges && (
          <button
            onClick={() => setChangesOpen(true)}
            className="flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            title="Request changes to this ontology"
          >
            <GitPullRequestArrow className="size-3.5" />
            Request changes
          </button>
        )}
      </div>

      {(graphStats.droppedRels > 0 || graphStats.isolatedCount > 0) && (
        <div className="absolute left-3 top-14 z-10 flex items-center gap-1.5 rounded-lg border border-chart-3/40 bg-chart-3/10 px-2.5 py-1 text-xs font-medium text-chart-3 shadow-sm backdrop-blur-sm">
          <AlertTriangle className="size-3.5" />
          {[
            graphStats.isolatedCount > 0 &&
              `${graphStats.isolatedCount} isolated ${graphStats.isolatedCount === 1 ? 'type' : 'types'}`,
            graphStats.droppedRels > 0 &&
              `${graphStats.droppedRels} relationship${graphStats.droppedRels === 1 ? '' : 's'} with unknown endpoints`,
          ]
            .filter(Boolean)
            .join(' · ')}
        </div>
      )}

      {changesOpen && onRequestChanges && (
        <RequestChangesModal
          onClose={() => setChangesOpen(false)}
          onSubmit={(changes) => {
            setChangesOpen(false)
            onRequestChanges(changes)
          }}
        />
      )}

      <GraphDetailPanel
        node={selectedNode}
        edge={selectedEdge}
        relationships={data.relationships}
        objectTypes={data.object_types}
        onClose={closePanel}
        onFocusNode={focusNode}
      />
    </div>
  )
}

export function OntologyGraph({ sessionId, onRequestChanges }: Props) {
  return (
    <ReactFlowProvider>
      <GraphInner sessionId={sessionId} onRequestChanges={onRequestChanges} />
    </ReactFlowProvider>
  )
}

export { CARDINALITY_LABEL }
