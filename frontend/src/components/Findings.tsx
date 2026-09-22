import { ArrowRight, FileCode2 } from 'lucide-react'
import type { Finding, Severity } from '../types'

const SEVERITY_STYLE: Record<Severity, string> = {
  high: 'bg-danger-50 text-danger-600 border-danger-200',
  medium: 'bg-warn-50 text-warn-600 border-warn-500/30',
  low: 'bg-slate-100 text-slate-500 border-slate-200',
}

interface FindingsProps {
  findings: Finding[]
  onSelect: (finding: Finding) => void
}

export function Findings({ findings, onSelect }: FindingsProps) {
  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Potential issues</h2>
        <span className="text-sm text-slate-500">{findings.length} found</span>
      </div>

      <ul className="flex flex-col gap-3">
        {findings.map((finding) => (
          <li key={finding.id}>
            <button
              type="button"
              onClick={() => onSelect(finding)}
              className="group flex w-full items-start gap-4 rounded-2xl border border-slate-200 bg-white/80 p-4 text-left shadow-sm shadow-slate-900/5 transition-all hover:border-brand-300 hover:shadow-md hover:shadow-brand-900/10"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <FileCode2 className="h-4 w-4" />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">{finding.title}</h3>
                  <span
                    className={[
                      'rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
                      SEVERITY_STYLE[finding.severity],
                    ].join(' ')}
                  >
                    {finding.severity}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-slate-500">{finding.description}</p>
                <p className="mt-2 font-mono text-xs text-slate-400">
                  {finding.file}:{finding.line}
                </p>
              </div>

              <ArrowRight className="mt-1.5 h-4 w-4 shrink-0 text-slate-300 transition-all group-hover:translate-x-0.5 group-hover:text-brand-500" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
