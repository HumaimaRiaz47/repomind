import { AnalysisProgress } from './components/AnalysisProgress'
import { ApplyFix } from './components/ApplyFix'
import { EvidenceView } from './components/EvidenceView'
import { Findings } from './components/Findings'
import { FinalReport } from './components/FinalReport'
import { RepositoryInput } from './components/RepositoryInput'
import { Header } from './components/layout/Header'
import { Stepper } from './components/layout/Stepper'
import { useRepoAnalysis } from './hooks/useRepoAnalysis'

function App() {
  const {
    step,
    repoUrl,
    stages,
    report,
    selectedFinding,
    evidence,
    evidenceLoading,
    fix,
    fixLoading,
    applyingFix,
    fixedFindingIds,
    startAnalysis,
    selectFinding,
    proceedToFix,
    applyFix,
    backToFindings,
    backToEvidence,
    finish,
    reset,
  } = useRepoAnalysis()

  return (
    <div className="min-h-screen w-full">
      <Header />
      <Stepper current={step} />

      <main className="px-4 pb-16 pt-8">
        {step === 'input' && <RepositoryInput onSubmit={startAnalysis} isSubmitting={false} />}

        {step === 'progress' && (
          <AnalysisProgress repoUrl={repoUrl} repo={report?.repo ?? null} stages={stages} />
        )}

        {step === 'findings' && report && (
          <Findings findings={report.findings} onSelect={selectFinding} />
        )}

        {step === 'evidence' && selectedFinding && (
          <EvidenceView
            finding={selectedFinding}
            evidence={evidence}
            isLoading={evidenceLoading}
            onBack={backToFindings}
            onProceedToFix={proceedToFix}
          />
        )}

        {step === 'fix' && selectedFinding && (
          <ApplyFix
            finding={selectedFinding}
            fix={fix}
            isLoading={fixLoading}
            isApplying={applyingFix}
            onBack={backToEvidence}
            onApply={applyFix}
            onFinish={finish}
          />
        )}

        {step === 'report' && report && (
          <FinalReport report={report} fixedFindingIds={fixedFindingIds} onReset={reset} />
        )}
      </main>
    </div>
  )
}

export default App
