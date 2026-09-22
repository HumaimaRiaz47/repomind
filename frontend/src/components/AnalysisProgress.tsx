import { Bot, Check, Cog, FileSearch, FolderGit2, Loader2, TestTube } from 'lucide-react'
import type { PipelineStage, RepoMeta } from '../types'

const STAGE_ICONS: Record<PipelineStage['id'], typeof FolderGit2> = {
  ingestion: FolderGit2,
  orchestrator: Cog,
  repo_analyzer: FileSearch,
  bug_hunter: Bot,
  test_generation: TestTube,
  validation: Check,
}

interface AnalysisProgressProps {
  repoUrl: string
  repo: RepoMeta | null
  stages: PipelineStage[]
}

export function AnalysisProgress({ repoUrl, repo, stages }: AnalysisProgressProps) {
  const doneCount = stages.filter((s) => s.status === 'done').length
  const percent = Math.round((doneCount / stages.length) * 100)

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="rounded-2xl border border-brand-100 bg-white/80 p-8 shadow-xl shadow-brand-900/5 backdrop-blur">
        <h2 className="text-lg font-semibold text-slate-900">Scanning repository</h2>
        <p className="mt-1 truncate text-sm text-slate-500">{repoUrl}</p>

        <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-600 transition-all duration-500"
            style={{ width: `${percent}%` }}
          />
        </div>
        <div className="mt-1.5 flex justify-between text-xs text-slate-400">
          <span>{percent}% complete</span>
          {repo && (
            <span>
              {repo.filesScanned} files · {repo.dependencies} dependencies · {repo.language}
            </span>
          )}
        </div>

        <ol className="mt-6 flex flex-col gap-1">
          {stages.map((stage) => {
            const Icon = STAGE_ICONS[stage.id]
            return (
              <li
                key={stage.id}
                className={[
                  'flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors',
                  stage.status === 'running' && 'bg-brand-50',
                ].join(' ')}
              >
                <div
                  className={[
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border',
                    stage.status === 'done' && 'border-ok-500/30 bg-ok-50 text-ok-600',
                    stage.status === 'running' && 'border-brand-300 bg-white text-brand-600',
                    stage.status === 'pending' && 'border-slate-200 bg-white text-slate-300',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {stage.status === 'running' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : stage.status === 'done' ? (
                    <Check className="h-4 w-4" strokeWidth={2.5} />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </div>
                <div className="min-w-0">
                  <p
                    className={[
                      'truncate text-sm font-medium',
                      stage.status === 'pending' ? 'text-slate-400' : 'text-slate-800',
                    ].join(' ')}
                  >
                    {stage.label}
                  </p>
                  <p className="truncate text-xs text-slate-400">{stage.description}</p>
                </div>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
