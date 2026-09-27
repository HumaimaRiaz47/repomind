import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Loader2,
  Minus,
  Plus,
} from 'lucide-react'
import type { Finding, FixSuggestion } from '../types'
import { CodeBlock } from './CodeBlock'

interface ApplyFixProps {
  finding: Finding
  fix: FixSuggestion | null
  isLoading: boolean
  isApplying: boolean
  onBack: () => void
  onApply: () => void
  onFinish: () => void
}

export function ApplyFix({
  finding,
  fix,
  isLoading,
  isApplying,
  onBack,
  onApply,
  onFinish,
}: ApplyFixProps) {
  return (
    <div className="mx-auto w-full max-w-2xl">

      {/* Back button */}
      <button
        type="button"
        onClick={onBack}
        className="mb-4 flex items-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-brand-600"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to evidence
      </button>

      {/* Main card */}
      <div className="rounded-2xl border border-slate-200 bg-white/80 p-6 shadow-sm shadow-slate-900/5">

        {/* Header */}
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            Fix Agent suggestion
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            {finding.title}
          </p>
        </div>

        {/* Loading */}
        {isLoading || !fix ? (
          <div className="mt-8 flex flex-col items-center gap-2 py-10 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" />

            <p className="text-sm">
              Fix Agent is drafting a patch…
            </p>
          </div>
        ) : (
          <div className="mt-6 flex flex-col gap-5">

            {/* Explanation */}
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-sm text-slate-600">
                {fix.explanation}
              </p>
            </div>

            {/* Code diff */}
            <section>
              <h3 className="mb-2 font-mono text-xs font-semibold text-slate-400">
                {fix.diff.file}
              </h3>

              <div className="flex flex-col gap-3">

                {/* Before */}
                <div>
                  <div className="mb-1 flex items-center gap-1 text-xs font-medium text-danger-600">
                    <Minus className="h-3 w-3" />
                    before
                  </div>

                  <CodeBlock
                    code={fix.diff.before}
                    tone="diff-before"
                  />
                </div>

                {/* After */}
                <div>
                  <div className="mb-1 flex items-center gap-1 text-xs font-medium text-ok-600">
                    <Plus className="h-3 w-3" />
                    after
                  </div>

                  <CodeBlock
                    code={fix.diff.after}
                    tone="diff-after"
                  />
                </div>

              </div>
            </section>

            {/* Verified regression result */}
            {fix.applied ? (
              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Regression validation
                </h3>

                <div className="flex items-center gap-2 rounded-lg border border-ok-500/30 bg-ok-50 px-3 py-2 text-sm font-medium text-ok-700">
                  <CheckCircle2 className="h-4 w-4" />

                  Regression suite verified
                </div>
              </section>
            ) : null}

            {/* Bottom action panel */}
            <div className="mt-1 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">

              {fix.applied ? (
                <>
                  {/* Verified state */}
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Fix verified
                    </p>

                    <p className="text-xs text-slate-500">
                      The patch was applied and regression validation succeeded.
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={onFinish}
                    className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-brand-600 to-brand-700 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-brand-600/20 transition-shadow hover:shadow-brand-600/30"
                  >
                    <Check className="h-4 w-4" />
                    View final report
                  </button>
                </>
              ) : (
                <>
                  {/* Not yet applied */}
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Review before applying
                    </p>

                    <p className="text-xs text-slate-500">
                      Runs the full regression suite after patching.
                    </p>
                  </div>

                  <button
                    type="button"
                    disabled={isApplying}
                    onClick={onApply}
                    className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-brand-600 to-brand-700 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-brand-600/20 transition-shadow hover:shadow-brand-600/30 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {isApplying ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Applying…
                      </>
                    ) : (
                      <>
                        <Check className="h-4 w-4" />
                        Apply Fix
                      </>
                    )}
                  </button>
                </>
              )}

            </div>
          </div>
        )}

      </div>
    </div>
  )
}