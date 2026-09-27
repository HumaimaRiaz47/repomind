import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Wrench,
  XCircle,
} from 'lucide-react'
import type { Finding, TestEvidence } from '../types'
import { CodeBlock } from './CodeBlock'

interface EvidenceViewProps {
  finding: Finding
  evidence: TestEvidence | null
  isLoading: boolean
  onBack: () => void
  onProceedToFix: () => void
}

export function EvidenceView({
  finding,
  evidence,
  isLoading,
  onBack,
  onProceedToFix,
}: EvidenceViewProps) {
  const result = evidence?.result

  const isFailed = result === 'fail'
  const isPassed = result === 'pass'
  const isSkipped = result === 'skipped'
  const isError = result === 'error'
  const isNeedsReview = result === 'needs_review'

  return (
    <div className="mx-auto w-full max-w-2xl">
      <button
        type="button"
        onClick={onBack}
        className="mb-4 flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-brand-600"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to findings
      </button>

      <div className="rounded-2xl border border-slate-200 bg-white/80 p-6 shadow-sm shadow-slate-900/5">
        <h2 className="text-lg font-semibold text-slate-900">
          {finding.title}
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          {finding.description}
        </p>

        <p className="mt-2 font-mono text-xs text-slate-400">
          {finding.file}:{finding.line}
        </p>

        {isLoading || !evidence ? (
          <div className="mt-8 flex flex-col items-center gap-2 py-10 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" />
            <p className="text-sm">
              Generating test &amp; running pytest…
            </p>
          </div>
        ) : (
          <div className="mt-6 flex flex-col gap-5">
            {/* Generated test */}
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Generated test
              </h3>

              <CodeBlock code={evidence.testCode} />
            </section>

            {/* pytest result */}
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                pytest result
              </h3>

              <div
                className={[
                  'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium',
                  isFailed &&
                    'border-danger-200 bg-danger-50 text-danger-700',
                  isPassed &&
                    'border-ok-500/30 bg-ok-50 text-ok-700',
                  (isSkipped || isError || isNeedsReview) &&
                    'border-amber-200 bg-amber-50 text-amber-700',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {isFailed ? (
                  <XCircle className="h-4 w-4" />
                ) : isPassed ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <AlertTriangle className="h-4 w-4" />
                )}

                {isFailed
                  ? 'Test failed against current code'
                  : isPassed
                    ? 'Test passed against current code'
                    : isSkipped
                      ? 'Test skipped — hypothesis not evaluated'
                      : isError
                        ? 'Test execution error'
                        : 'Test requires review'}
              </div>

              <CodeBlock code={evidence.output} tone="default" />
            </section>

            {/* Reasoning */}
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Reasoning
              </h3>

              <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                {evidence.reasoning}
              </p>
            </section>

            {/* Decision */}
            <div className="mt-1 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              {isFailed ? (
                <>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Validated
                    </p>

                    <p className="text-xs text-slate-500">
                      Bug confirmed — ready to generate a fix.
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={onProceedToFix}
                    className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-brand-600 to-brand-700 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-brand-600/20 hover:shadow-brand-600/30"
                  >
                    <Wrench className="h-4 w-4" />
                    Generate Fix
                  </button>
                </>
              ) : isPassed ? (
                <>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      Rejected
                    </p>

                    <p className="text-xs text-slate-500">
                      Test passed — this hypothesis was not reproduced.
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={onBack}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Back to findings
                  </button>
                </>
              ) : (
                <>
                  <div>
                    <p className="text-sm font-semibold text-amber-700">
                      Test Generation Error
                    </p>

                    <p className="text-xs text-slate-500">
                      The generated test did not successfully evaluate the
                      hypothesis. No fix will be generated.
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={onBack}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Back to findings
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