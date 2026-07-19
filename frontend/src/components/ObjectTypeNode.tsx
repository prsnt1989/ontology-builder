import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import {
  Box,
  Building2,
  Cloud,
  Server,
  Wallet,
  Briefcase,
  Users,
  User,
  FileText,
  Boxes,
  Ticket,
  ClipboardList,
  Network,
  type LucideIcon,
} from 'lucide-react'
import type { GraphObjectType } from '../lib/api'
import { cn } from '../lib/utils'

const ICON_MAP: Record<string, LucideIcon> = {
  building: Building2,
  cloud: Cloud,
  server: Server,
  wallet: Wallet,
  briefcase: Briefcase,
  users: Users,
  user: User,
  person: User,
  team: Users,
  file: FileText,
  document: FileText,
  box: Box,
  boxes: Boxes,
  ticket: Ticket,
  case: ClipboardList,
  task: ClipboardList,
  network: Network,
}

export interface ObjectTypeNodeData {
  objectType: GraphObjectType
  [key: string]: unknown
}

function iconFor(hint?: string | null): LucideIcon {
  if (!hint) return Box
  const key = hint.toLowerCase()
  return ICON_MAP[key] ?? Box
}

export const ObjectTypeNode = memo(function ObjectTypeNode({
  data,
  selected,
}: NodeProps) {
  const nodeData = data as ObjectTypeNodeData & { isolated?: boolean }
  const { objectType: ot } = nodeData
  const isolated = !!nodeData.isolated
  const Icon = iconFor(ot.icon)
  const props = ot.properties ?? []
  const preview = props.slice(0, 3).map((p) => p.name)

  return (
    <div
      title={isolated ? 'Not connected to any other object type' : undefined}
      className={cn(
        'w-[220px] overflow-hidden rounded-xl bg-card text-card-foreground shadow-sm ring-1 transition-shadow',
        selected
          ? 'ring-2 ring-primary'
          : isolated
            ? 'ring-2 ring-chart-3/60 hover:shadow-md'
            : 'ring-foreground/10 hover:shadow-md'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-2 !border-0 !bg-primary/60"
      />
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold leading-tight">{ot.display_name}</div>
          <div className="truncate font-mono text-[10px] text-muted-foreground">{ot.api_name}</div>
        </div>
      </div>
      <div className="px-3 py-2">
        <div className="text-[11px] font-medium text-muted-foreground">
          {props.length} {props.length === 1 ? 'property' : 'properties'}
        </div>
        {preview.length > 0 && (
          <div className="mt-1 truncate font-mono text-[10px] text-foreground/60">
            {preview.join(' · ')}
            {props.length > preview.length ? ' …' : ''}
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!size-2 !border-0 !bg-primary/60"
      />
    </div>
  )
})
