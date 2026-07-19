import { X, ArrowRight, KeyRound, Hash, Table2 } from 'lucide-react'
import type { GraphObjectType, GraphRelationship } from '../lib/api'
import { Badge } from './ui/badge'
import { cn } from '../lib/utils'

export const CARDINALITY_LABEL: Record<string, string> = {
  one_to_one: 'one → one',
  one_to_many: 'one → many',
  many_to_one: 'many → one',
  many_to_many: 'many ↔ many',
}

interface Props {
  node: GraphObjectType | null
  edge: GraphRelationship | null
  relationships: GraphRelationship[]
  objectTypes: GraphObjectType[]
  onClose: () => void
  onFocusNode: (apiName: string) => void
}

export function GraphDetailPanel({
  node,
  edge,
  relationships,
  objectTypes,
  onClose,
  onFocusNode,
}: Props) {
  if (!node && !edge) return null

  const displayName = (apiName: string) =>
    objectTypes.find((o) => o.api_name === apiName)?.display_name ?? apiName

  return (
    <div className="absolute right-0 top-0 z-10 flex h-full w-80 flex-col border-l border-border bg-card/95 backdrop-blur-sm">
      <div className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold">{node ? node.display_name : edge?.display_name}</div>
          <div className="truncate font-mono text-[11px] text-muted-foreground">
            {node ? node.api_name : edge?.api_name}
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Close"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {node && <NodeDetail node={node} relationships={relationships} displayName={displayName} onFocusNode={onFocusNode} />}
        {edge && <EdgeDetail edge={edge} displayName={displayName} onFocusNode={onFocusNode} />}
      </div>
    </div>
  )
}

function NodeDetail({
  node,
  relationships,
  displayName,
  onFocusNode,
}: {
  node: GraphObjectType
  relationships: GraphRelationship[]
  displayName: (a: string) => string
  onFocusNode: (a: string) => void
}) {
  const props = node.properties ?? []
  const outbound = relationships.filter((r) => r.from_object_type === node.api_name)
  const inbound = relationships.filter((r) => r.to_object_type === node.api_name)

  return (
    <div className="space-y-4">
      {node.description && <p className="text-sm text-muted-foreground">{node.description}</p>}

      <div className="flex flex-wrap gap-1.5">
        {node.backing_table?.table_name && (
          <Badge variant="secondary" className="gap-1">
            <Table2 className="size-3" />
            {node.backing_table.table_name}
          </Badge>
        )}
        {node.primary_key && (
          <Badge variant="outline" className="gap-1">
            <KeyRound className="size-3" />
            {node.primary_key}
          </Badge>
        )}
      </div>

      <div>
        <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Properties ({props.length})
        </div>
        <div className="overflow-hidden rounded-lg border border-border">
          {props.map((p, i) => (
            <div
              key={p.name}
              className={cn(
                'flex items-center justify-between gap-2 px-2.5 py-1.5',
                i > 0 && 'border-t border-border'
              )}
            >
              <div className="min-w-0">
                <div className="truncate font-mono text-xs">{p.name}</div>
                {p.type && <div className="text-[10px] text-muted-foreground">{p.type}</div>}
              </div>
              <div className="flex shrink-0 gap-1">
                {p.required && <Badge variant="warning" className="px-1.5 py-0 text-[10px]">req</Badge>}
                {p.indexed && (
                  <Badge variant="info" className="gap-0.5 px-1.5 py-0 text-[10px]">
                    <Hash className="size-2.5" />
                    idx
                  </Badge>
                )}
              </div>
            </div>
          ))}
          {props.length === 0 && (
            <div className="px-2.5 py-3 text-center text-xs text-muted-foreground">No properties</div>
          )}
        </div>
      </div>

      {outbound.length > 0 && (
        <RelList title={`Outgoing (${outbound.length})`} rels={outbound} peerKey="to_object_type" displayName={displayName} onFocusNode={onFocusNode} />
      )}
      {inbound.length > 0 && (
        <RelList title={`Incoming (${inbound.length})`} rels={inbound} peerKey="from_object_type" displayName={displayName} onFocusNode={onFocusNode} />
      )}
    </div>
  )
}

function RelList({
  title,
  rels,
  peerKey,
  displayName,
  onFocusNode,
}: {
  title: string
  rels: GraphRelationship[]
  peerKey: 'to_object_type' | 'from_object_type'
  displayName: (a: string) => string
  onFocusNode: (a: string) => void
}) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
      <div className="space-y-1">
        {rels.map((r) => (
          <button
            key={r.api_name}
            onClick={() => onFocusNode(r[peerKey])}
            className="flex w-full items-center justify-between gap-2 rounded-md border border-border px-2.5 py-1.5 text-left transition-colors hover:border-primary/40 hover:bg-accent"
          >
            <div className="min-w-0">
              <div className="truncate text-xs font-medium">{r.display_name}</div>
              <div className="flex items-center gap-1 truncate text-[10px] text-muted-foreground">
                <ArrowRight className="size-2.5" />
                {displayName(r[peerKey])}
              </div>
            </div>
            <Badge variant="secondary" className="shrink-0 px-1.5 py-0 text-[10px]">
              {CARDINALITY_LABEL[r.cardinality] ?? r.cardinality}
            </Badge>
          </button>
        ))}
      </div>
    </div>
  )
}

function EdgeDetail({
  edge,
  displayName,
  onFocusNode,
}: {
  edge: GraphRelationship
  displayName: (a: string) => string
  onFocusNode: (a: string) => void
}) {
  return (
    <div className="space-y-4">
      {edge.description && <p className="text-sm text-muted-foreground">{edge.description}</p>}

      <div className="flex items-center gap-2 rounded-lg border border-border p-3 text-sm">
        <button
          onClick={() => onFocusNode(edge.from_object_type)}
          className="min-w-0 flex-1 truncate rounded px-1 text-left font-medium hover:text-primary"
        >
          {displayName(edge.from_object_type)}
        </button>
        <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
        <button
          onClick={() => onFocusNode(edge.to_object_type)}
          className="min-w-0 flex-1 truncate rounded px-1 text-right font-medium hover:text-primary"
        >
          {displayName(edge.to_object_type)}
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge variant="info">{CARDINALITY_LABEL[edge.cardinality] ?? edge.cardinality}</Badge>
        {edge.is_required && <Badge variant="warning">required</Badge>}
      </div>
    </div>
  )
}
