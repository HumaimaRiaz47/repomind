import { useCallback, useState } from 'react'
import { initialStages } from '../data/mockData'
import { applyFix as applyFixRequest, fetchEvidence, fetchFix, runAnalysis } from '../services/api'
import type {
  AnalysisReport,
  Finding,
  FixSuggestion,
  PipelineStage,
  PipelineStageId,
  TestEvidence,
  WizardStep,
} from '../types'

export function useRepoAnalysis() {
  const [step, setStep] = useState<WizardStep>('input')
  const [repoUrl, setRepoUrl] = useState('')
  const [stages, setStages] = useState<PipelineStage[]>(initialStages)
  const [report, setReport] = useState<AnalysisReport | null>(null)

  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null)
  const [evidence, setEvidence] = useState<TestEvidence | null>(null)
  const [evidenceLoading, setEvidenceLoading] = useState(false)

  const [fix, setFix] = useState<FixSuggestion | null>(null)
  const [fixLoading, setFixLoading] = useState(false)
  const [applyingFix, setApplyingFix] = useState(false)
  const [fixedFindingIds, setFixedFindingIds] = useState<string[]>([])

  const markStage = useCallback((stageId: PipelineStageId) => {
    setStages((prev) =>
      prev.map((s) => {
        if (s.id === stageId) return { ...s, status: 'running' }
        if (s.status === 'running') return { ...s, status: 'done' }
        return s
      }),
    )
  }, [])

  const startAnalysis = useCallback(
    async (url: string) => {
      setRepoUrl(url)
      setStages(initialStages)
      setStep('progress')

      const result = await runAnalysis(url, markStage)
      setStages((prev) => prev.map((s) => ({ ...s, status: 'done' })))
      setReport(result)
      setStep('findings')
    },
    [markStage],
  )

  const selectFinding = useCallback(async (finding: Finding) => {
    setSelectedFinding(finding)
    setEvidence(null)
    setFix(null)
    setStep('evidence')
    setEvidenceLoading(true)
    const result = await fetchEvidence(finding)
    setEvidence(result)
    setEvidenceLoading(false)
  }, [])

  const proceedToFix = useCallback(async () => {
    if (!selectedFinding) return
    setStep('fix')
    setFixLoading(true)
    const result = await fetchFix(selectedFinding)
    setFix(result)
    setFixLoading(false)
  }, [selectedFinding])

  const applyFix = useCallback(async () => {
    if (!selectedFinding) return
    setApplyingFix(true)
    const result = await applyFixRequest(selectedFinding.id)
    setFix(result)
    setFixedFindingIds((prev) => [...prev, selectedFinding.id])
    setApplyingFix(false)
  }, [selectedFinding])

  const backToFindings = useCallback(() => {
    setStep('findings')
    setSelectedFinding(null)
    setEvidence(null)
    setFix(null)
  }, [])

  const backToEvidence = useCallback(() => {
    setStep('evidence')
  }, [])

  const finish = useCallback(() => setStep('report'), [])

  const reset = useCallback(() => {
    setStep('input')
    setRepoUrl('')
    setStages(initialStages)
    setReport(null)
    setSelectedFinding(null)
    setEvidence(null)
    setFix(null)
    setFixedFindingIds([])
  }, [])

  return {
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
  }
}
