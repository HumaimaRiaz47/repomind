import { Bug, CheckCircle2, FileCheck2, RotateCcw, ShieldCheck } from 'lucide-react'
import type { AnalysisReport } from '../types'

interface FinalReportProps {
  report: AnalysisReport
  fixedFindingIds: string[]
  onReset: () => void
}

export function FinalReport({ report, fixedFindingIds, onReset }: FinalReportProps) {
  const metrics = [
    { label: 'Issues found', value: report.issuesFound, icon: Bug, tone: 'text-slate-600 bg-slate-100' },
    { label: 'Validated', value: report.issuesValidated, icon: ShieldCheck, tone: 'text-brand-600 bg-brand-50' },
    { label: 'Fixed', value: fixedFindingIds.length, icon: CheckCircle2, tone: 'text-ok-600 bg-ok-50' },
    { label: 'Tests generated', value: report.testsGenerated, icon: FileCheck2, tone: 'text-warn-600 bg-warn-50' },
  ]

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="rounded-2xl border border-brand-100 bg-white/80 p-8 shadow-xl shadow-brand-900/5">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-ok-50 text-ok-600">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900">Analysis complete</h2>
          <p className="mt-1 text-sm text-slate-500">
            {report.repo.owner}/{report.repo.name}
          </p>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {metrics.map((m) => (
            <div key={m.label} className="rounded-xl border border-slate-200 bg-white p-3 text-center">
              <div className={['mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg', m.tone].join(' ')}>
                <m.icon className="h-4 w-4" />
              </div>
              <p className="text-lg font-bold text-slate-900">{m.value}</p>
              <p className="text-[11px] text-slate-500">{m.label}</p>
            </div>
          ))}
        </div>

        <div className="mt-6">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Findings summary
          </h3>
          <ul className="flex flex-col gap-2">
            {report.findings.map((f) => {
              const wasFixed = fixedFindingIds.includes(f.id)
              const wasRejected = f.status === 'rejected'
              const label = wasFixed ? 'Fixed' : wasRejected ? 'Rejected' : 'Validated'
              const style = wasFixed
                ? 'bg-ok-50 text-ok-700 border-ok-500/30'
                : wasRejected
                  ? 'bg-slate-100 text-slate-500 border-slate-200'
                  : 'bg-brand-50 text-brand-700 border-brand-200'
              return (
                <li
                  key={f.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2"
                >
                  <span className="truncate text-sm text-slate-700">{f.title}</span>
                  <span className={['shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold', style].join(' ')}>
                    {label}
                  </span>
                </li>
              )
            })}
          </ul>
        </div>

        <button
          type="button"
          onClick={onReset}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 transition-colors hover:border-brand-300 hover:text-brand-600"
        >
          <RotateCcw className="h-4 w-4" />
          Analyze another repository
        </button>
      </div>
    </div>
  )
}
