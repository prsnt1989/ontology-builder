import { useState, useEffect } from 'react'
import {
  Box,
  List,
  ArrowLeftRight,
  Zap,
  Lock,
  CheckCircle2,
  RefreshCw,
  Table2,
  FileCode2,
  Network,
  GitPullRequestArrow,
} from 'lucide-react'
import { getOntologyFiles, getOntologyFileContent } from '../lib/api'
import type { OntologyFileInfo } from '../lib/api'
import { OntologyGraph } from './OntologyGraph'
import { RequestChangesModal } from './RequestChangesModal'
import { cn } from '../lib/utils'

export type ViewTab = 'yaml' | 'graph' | 'update'

interface Props {
  sessionId: string
  onRequestChanges?: (changes: string[]) => void
  /** Controlled tab (optional — falls back to internal state when omitted). */
  tab?: ViewTab
  onTabChange?: (tab: ViewTab) => void
  /** Show the Update tab (only once an update run has started). */
  showUpdateTab?: boolean
  /** Content rendered in the Update tab (chat + timeline + activity). */
  updateSlot?: React.ReactNode
}

const FILE_ICONS: Record<string, typeof Box> = {
  'object_types.yaml': Box,
  'properties.yaml': List,
  'relationships.yaml': ArrowLeftRight,
  'actions.yaml': Zap,
  'permissions.yaml': Lock,
  'validation_rules.yaml': CheckCircle2,
  'lifecycle_states.yaml': RefreshCw,
  'data_mapping.yaml': Table2,
}

const FILE_DESCRIPTIONS: Record<string, string> = {
  'object_types.yaml': 'Entity definitions',
  'properties.yaml': 'Field schemas per type',
  'relationships.yaml': 'Connections between entities',
  'actions.yaml': 'Operations & workflows',
  'permissions.yaml': 'Access control rules',
  'validation_rules.yaml': 'Constraints & checks',
  'lifecycle_states.yaml': 'State machines',
  'data_mapping.yaml': 'DB table mappings',
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB`
}

export function OntologyViewer({
  sessionId,
  onRequestChanges,
  tab: tabProp,
  onTabChange,
  showUpdateTab = false,
  updateSlot,
}: Props) {
  const [files, setFiles] = useState<OntologyFileInfo[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [internalTab, setInternalTab] = useState<ViewTab>('yaml')
  const [changesOpen, setChangesOpen] = useState(false)

  // Controlled when `tab` prop is provided; otherwise self-managed.
  const tab = tabProp ?? internalTab
  const setTab = (t: ViewTab) => (onTabChange ? onTabChange(t) : setInternalTab(t))

  useEffect(() => {
    getOntologyFiles(sessionId)
      .then((res) => {
        setFiles(res.files)
        if (res.files.length > 0) {
          loadFile(res.files[0].name)
        }
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const loadFile = async (filename: string) => {
    setLoading(true)
    setSelectedFile(filename)
    try {
      const text = await getOntologyFileContent(sessionId, filename)
      setContent(text)
    } catch {
      setContent('# Error loading file')
    } finally {
      setLoading(false)
    }
  }

  const SelectedIcon = selectedFile ? FILE_ICONS[selectedFile] || FileCode2 : FileCode2

  return (
    <div className="flex h-full flex-col">
      {/* View toggle */}
      <div className="flex items-center gap-1 border-b border-border px-4 py-2">
        <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5">
          <button
            onClick={() => setTab('yaml')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors',
              tab === 'yaml' ? 'bg-card text-foreground shadow-sm ring-1 ring-foreground/10' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <FileCode2 className="size-3.5" />
            YAML
          </button>
          <button
            onClick={() => setTab('graph')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors',
              tab === 'graph' ? 'bg-card text-foreground shadow-sm ring-1 ring-foreground/10' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Network className="size-3.5" />
            Graph
          </button>
          {showUpdateTab && (
            <button
              onClick={() => setTab('update')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors',
                tab === 'update' ? 'bg-card text-foreground shadow-sm ring-1 ring-foreground/10' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <GitPullRequestArrow className="size-3.5" />
              Update
            </button>
          )}
        </div>
        {onRequestChanges && (
          <button
            onClick={() => setChangesOpen(true)}
            className="ml-auto flex items-center gap-1.5 rounded-md bg-primary px-3 py-1 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            title="Request changes to this ontology"
          >
            <GitPullRequestArrow className="size-3.5" />
            Request changes
          </button>
        )}
      </div>

      {changesOpen && onRequestChanges && (
        <RequestChangesModal
          onClose={() => setChangesOpen(false)}
          onSubmit={(changes) => {
            setChangesOpen(false)
            onRequestChanges(changes)
          }}
        />
      )}

      {tab === 'update' ? (
        <div className="min-h-0 flex-1">{updateSlot}</div>
      ) : tab === 'graph' ? (
        <div className="min-h-0 flex-1">
          <OntologyGraph sessionId={sessionId} />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
      {/* Sidebar */}
      <div className="w-72 shrink-0 overflow-y-auto border-r border-border bg-sidebar p-3">
        <h3 className="px-2 pb-2 pt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Generated Files
        </h3>
        <div className="space-y-0.5">
          {files.map((f) => {
            const Icon = FILE_ICONS[f.name] || FileCode2
            const active = selectedFile === f.name
            return (
              <button
                key={f.name}
                onClick={() => loadFile(f.name)}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors',
                  active
                    ? 'bg-accent text-accent-foreground'
                    : 'text-sidebar-foreground/80 hover:bg-muted'
                )}
              >
                <Icon className="size-4 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{f.name}</div>
                  <div className="flex justify-between gap-2 text-xs text-muted-foreground">
                    <span className="truncate">{FILE_DESCRIPTIONS[f.name] || ''}</span>
                    <span className="shrink-0">{formatSize(f.size)}</span>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {selectedFile && (
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <div className="flex items-center gap-2">
              <SelectedIcon className="size-4 text-muted-foreground" />
              <span className="font-medium">{selectedFile}</span>
            </div>
            <span className="text-xs text-muted-foreground">
              {FILE_DESCRIPTIONS[selectedFile] || ''}
            </span>
          </div>
        )}

        <div className="flex-1 overflow-auto">
          {!selectedFile && (
            <div className="mt-20 text-center text-sm text-muted-foreground">
              Select a file to view its contents
            </div>
          )}
          {selectedFile && loading && (
            <div className="p-5 text-sm text-muted-foreground">Loading…</div>
          )}
          {selectedFile && !loading && (
            <pre className="p-5 text-sm leading-relaxed font-mono whitespace-pre-wrap">
              <YamlHighlight content={content} />
            </pre>
          )}
        </div>
      </div>
        </div>
      )}
    </div>
  )
}

function YamlHighlight({ content }: { content: string }) {
  const lines = content.split('\n')
  return (
    <>
      {lines.map((line, i) => (
        <div key={i} className="-mx-2 rounded px-2 hover:bg-muted/40">
          <YamlLine line={line} />
        </div>
      ))}
    </>
  )
}

function YamlLine({ line }: { line: string }) {
  if (!line.trim()) return <span>{'\n'}</span>

  if (line.trimStart().startsWith('#')) {
    return <span className="italic text-muted-foreground">{line}</span>
  }

  const keyMatch = line.match(/^(\s*)(- )?([a-zA-Z_][a-zA-Z0-9_]*):(.*)$/)
  if (keyMatch) {
    const [, indent, dash, key, value] = keyMatch
    const trimmedVal = value.trim()

    let valElement: React.ReactNode = null
    if (trimmedVal === '' || trimmedVal === 'null') {
      valElement = trimmedVal ? <span className="text-muted-foreground">{value}</span> : null
    } else if (trimmedVal === 'true' || trimmedVal === 'false') {
      valElement = <span className="text-chart-3">{value}</span>
    } else if (trimmedVal.startsWith("'") || trimmedVal.startsWith('"')) {
      valElement = <span className="text-chart-2">{value}</span>
    } else if (/^-?\d+(\.\d+)?$/.test(trimmedVal)) {
      valElement = <span className="text-chart-4">{value}</span>
    } else {
      valElement = <span className="text-chart-2">{value}</span>
    }

    return (
      <span>
        {indent}
        {dash && <span className="text-muted-foreground">- </span>}
        <span className="font-medium text-primary">{key}</span>
        <span className="text-muted-foreground">:</span>
        {valElement}
      </span>
    )
  }

  if (line.trimStart().startsWith('- ')) {
    const indent = line.match(/^(\s*)/)?.[1] || ''
    const val = line.trimStart().slice(2)
    return (
      <span>
        {indent}
        <span className="text-muted-foreground">- </span>
        <span className="text-chart-2">{val}</span>
      </span>
    )
  }

  return <span className="text-chart-2">{line}</span>
}
