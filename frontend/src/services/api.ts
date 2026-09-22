// Mock service layer standing in for the FastAPI backend (see system_design.png).
// Each function returns a Promise so it can be swapped for a real `fetch("/api/...")`
// call later without changing any component code.

import { mockEvidence, mockFindings, mockFixes, mockRepoMeta } from '../data/mockData'
import type { AnalysisReport, Finding, FixSuggestion, PipelineStageId, TestEvidence } from '../types'

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const GITHUB_URL_RE = /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/

export function validateRepoUrl(url: string): string | null {
  if (!url.trim()) return 'Enter a GitHub repository URL.'
  if (!GITHUB_URL_RE.test(url.trim())) {
    return 'Enter a valid URL like https://github.com/owner/repo'
  }
  return null
}

export async function runAnalysis(
  url: string,
  onStage: (stageId: PipelineStageId) => void,
): Promise<AnalysisReport> {
  const stageOrder: PipelineStageId[] = [
    'ingestion',
    'orchestrator',
    'repo_analyzer',
    'bug_hunter',
    'test_generation',
    'validation',
  ]

  for (const stageId of stageOrder) {
    onStage(stageId)
    await delay(650)
  }

  const repo = mockRepoMeta(url)
  const findings = mockFindings

  return {
    repo,
    findings,
    issuesFound: findings.length,
    issuesValidated: findings.filter((f) => mockEvidence[f.id]?.result === 'fail').length,
    issuesFixed: 0,
    testsGenerated: findings.length,
    generatedAt: new Date().toISOString(),
  }
}

export async function fetchEvidence(finding: Finding): Promise<TestEvidence> {
  await delay(400)
  return mockEvidence[finding.id]
}

export async function fetchFix(finding: Finding): Promise<FixSuggestion> {
  await delay(400)
  return mockFixes[finding.id]
}

export async function applyFix(findingId: string): Promise<FixSuggestion> {
  await delay(700)
  const fix = mockFixes[findingId]
  return { ...fix, applied: true }
}
