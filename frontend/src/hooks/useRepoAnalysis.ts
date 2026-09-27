import { useCallback, useState } from 'react'
import { initialStages } from '../data/mockData'
import {
  fetchEvidence,
  fetchFix,
  runAnalysis,
} from '../services/api'
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
  const [step, setStep] =
    useState<WizardStep>('input')

  const [repoUrl, setRepoUrl] =
    useState('')

  const [stages, setStages] =
    useState<PipelineStage[]>(initialStages)

  const [report, setReport] =
    useState<AnalysisReport | null>(null)

  const [analysisError, setAnalysisError] =
    useState<string | null>(null)

  const [selectedFinding, setSelectedFinding] =
    useState<Finding | null>(null)

  const [evidence, setEvidence] =
    useState<TestEvidence | null>(null)

  const [evidenceLoading, setEvidenceLoading] =
    useState(false)

  const [fix, setFix] =
    useState<FixSuggestion | null>(null)

  const [fixLoading, setFixLoading] =
    useState(false)

  const [applyingFix, setApplyingFix] =
    useState(false)

  const [fixedFindingIds, setFixedFindingIds] =
    useState<string[]>([])

  // ---------------------------------------------------------------------------
  // Pipeline stages
  // ---------------------------------------------------------------------------

  const markStage = useCallback(
    (stageId: PipelineStageId) => {
      setStages((previous) =>
        previous.map((stage) => {
          if (stage.id === stageId) {
            return {
              ...stage,
              status: 'running',
            }
          }

          if (stage.status === 'running') {
            return {
              ...stage,
              status: 'done',
            }
          }

          return stage
        }),
      )
    },
    [],
  )

  // ---------------------------------------------------------------------------
  // Start analysis
  // ---------------------------------------------------------------------------

  const startAnalysis = useCallback(
    async (url: string) => {
      setRepoUrl(url)
      setStages(initialStages)
      setAnalysisError(null)
      setSelectedFinding(null)
      setEvidence(null)
      setFix(null)
      setFixedFindingIds([])
      setStep('progress')

      try {
        const result = await runAnalysis(
          url,
          markStage,
        )

        setStages((previous) =>
          previous.map((stage) => ({
            ...stage,
            status: 'done',
          })),
        )

        setReport(result)
        setStep('findings')
      } catch (error: unknown) {
        setStages((previous) =>
          previous.map((stage) =>
            stage.status === 'running'
              ? {
                  ...stage,
                  status: 'error',
                }
              : stage,
          ),
        )

        const message =
          error instanceof Error
            ? error.message
            : 'An unexpected error occurred.'

        setAnalysisError(message)
        setStep('input')
      }
    },
    [markStage],
  )

  // ---------------------------------------------------------------------------
  // Select finding
  // ---------------------------------------------------------------------------

  const selectFinding = useCallback(
    async (finding: Finding) => {
      setSelectedFinding(finding)
      setEvidence(null)
      setFix(null)
      setStep('evidence')
      setEvidenceLoading(true)

      try {
        const result =
          await fetchEvidence(finding)

        setEvidence(result)
      } finally {
        setEvidenceLoading(false)
      }
    },
    [],
  )

  // ---------------------------------------------------------------------------
  // Generate/display fix
  // ---------------------------------------------------------------------------

  const proceedToFix = useCallback(
    async () => {
      if (!selectedFinding) {
        return
      }

      setStep('fix')
      setFix(null)
      setFixLoading(true)

      try {
        const result =
          await fetchFix(selectedFinding)

        setFix(result)
      } finally {
        setFixLoading(false)
      }
    },
    [selectedFinding],
  )

  // ---------------------------------------------------------------------------
  // Apply / confirm backend-generated fix
  // ---------------------------------------------------------------------------
const applyFix = useCallback(async () => {
  if (!selectedFinding || !fix) {
    return
  }

  setApplyingFix(true)

  try {
    // The backend already performs the patch during the analysis pipeline.
    // The Apply Fix button is the UI confirmation step.
    const appliedFix: FixSuggestion = {
      ...fix,
      applied: true,
    }

    setFix(appliedFix)

    setFixedFindingIds((previous) =>
      previous.includes(selectedFinding.id)
        ? previous
        : [...previous, selectedFinding.id],
    )
  } finally {
    setApplyingFix(false)
  }
}, [selectedFinding, fix])

  // ---------------------------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------------------------

  const backToFindings = useCallback(() => {
    setStep('findings')
    setSelectedFinding(null)
    setEvidence(null)
    setFix(null)
  }, [])

  const backToEvidence = useCallback(() => {
    setStep('evidence')
  }, [])

  const finish = useCallback(() => {
    setStep('report')
  }, [])

  // ---------------------------------------------------------------------------
  // Reset
  // ---------------------------------------------------------------------------

  const reset = useCallback(() => {
    setStep('input')
    setRepoUrl('')
    setStages(initialStages)
    setReport(null)
    setAnalysisError(null)
    setSelectedFinding(null)
    setEvidence(null)
    setEvidenceLoading(false)
    setFix(null)
    setFixLoading(false)
    setApplyingFix(false)
    setFixedFindingIds([])
  }, [])

  return {
    step,
    repoUrl,
    stages,
    report,
    analysisError,

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