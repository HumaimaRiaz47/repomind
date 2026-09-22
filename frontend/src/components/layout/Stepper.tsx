import { Check, ClipboardList, Link2, ListChecks, ScanSearch, Search, Wrench } from 'lucide-react'
import type { WizardStep } from '../../types'

const STEPS: { id: WizardStep; label: string; icon: typeof Link2 }[] = [
  { id: 'input', label: 'Repository Input', icon: Link2 },
  { id: 'progress', label: 'Analysis Progress', icon: ScanSearch },
  { id: 'findings', label: 'Findings', icon: ListChecks },
  { id: 'evidence', label: 'Evidence View', icon: Search },
  { id: 'fix', label: 'Apply Fix', icon: Wrench },
  { id: 'report', label: 'Final Report', icon: ClipboardList },
]

export function Stepper({ current }: { current: WizardStep }) {
  const currentIndex = STEPS.findIndex((s) => s.id === current)

  return (
    <nav aria-label="Analysis progress" className="mx-auto w-full max-w-4xl px-4">
      <ol className="scroll-thin flex items-start gap-1 overflow-x-auto pb-2">
        {STEPS.map((step, index) => {
          const state = index < currentIndex ? 'done' : index === currentIndex ? 'active' : 'upcoming'
          const Icon = step.icon
          return (
            <li key={step.id} className="flex flex-1 items-center last:flex-none">
              <div className="flex min-w-[84px] flex-col items-center gap-1.5 text-center">
                <div
                  className={[
                    'flex h-9 w-9 items-center justify-center rounded-full border-2 transition-colors',
                    state === 'done' && 'border-brand-600 bg-brand-600 text-white',
                    state === 'active' && 'border-brand-600 bg-white text-brand-600 ring-4 ring-brand-100',
                    state === 'upcoming' && 'border-slate-200 bg-white text-slate-300',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {state === 'done' ? <Check className="h-4 w-4" strokeWidth={2.5} /> : <Icon className="h-4 w-4" strokeWidth={2.25} />}
                </div>
                <span
                  className={[
                    'text-[11px] font-medium leading-tight',
                    state === 'upcoming' ? 'text-slate-400' : 'text-slate-700',
                  ].join(' ')}
                >
                  {step.label}
                </span>
              </div>
              {index < STEPS.length - 1 && (
                <div
                  className={[
                    'mx-1 mt-[-18px] h-0.5 flex-1 rounded-full',
                    index < currentIndex ? 'bg-brand-600' : 'bg-slate-200',
                  ].join(' ')}
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
