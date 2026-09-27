// Domain types for the RepoMind analysis pipeline (see system_design.png).
// These mirror the backend's eventual API response shapes so the mock
// service layer can be swapped for real `fetch` calls without touching UI.

export type PipelineStageId =
  | 'ingestion'
  | 'orchestrator'
  | 'repo_analyzer'
  | 'bug_hunter'
  | 'test_generation'
  | 'validation'

export type StageStatus = 'pending' | 'running' | 'done' | 'error'

export interface PipelineStage {
  id: PipelineStageId
  label: string
  description: string
  status: StageStatus
}

export type Severity = 'high' | 'medium' | 'low'

export interface Finding {
  id: string
  title: string
  description: string
  severity: Severity
  file: string
  line: number
  agent: 'Bug Hunter Agent'
  status: 'pending' | 'validated' | 'rejected' | 'fixed'
}

export interface TestEvidence {
  findingId: string
  testCode: string
  testFramework: 'pytest'
  result: 'pass' | 'fail' | 'skipped' | 'error' | 'needs_review'
  output: string
  reasoning: string
}

export interface FixSuggestion {
  findingId: string
  explanation: string
  diff: {
    file: string
    before: string
    after: string
  }
  regressionTests: {
    total: number
    passed: number
  }
  applied: boolean
}

export interface RepoMeta {
  url: string
  owner: string
  name: string
  language: string
  filesScanned: number
  dependencies: number
}

export interface AnalysisReport {
  repo: RepoMeta
  findings: Finding[]
  issuesFound: number
  issuesValidated: number
  issuesFixed: number
  testsGenerated: number
  generatedAt: string
}

export type WizardStep =
  | 'input'
  | 'progress'
  | 'findings'
  | 'evidence'
  | 'fix'
  | 'report'

// ------------------------------------------------------------------
// Backend result detail (attached to findings as _result by /report)
// ------------------------------------------------------------------

export interface BackendExecution {
  status: 'passed' | 'failed' | 'error' | 'timeout' | 'skipped'
  return_code: number | null
  stdout: string
  stderr: string
}

export interface BackendValidation {
  status:
    | 'validated'
    | 'rejected'
    | 'needs_review'
    | 'test_generation_error'
  confidence: number
  reason: string
}

export interface BackendFix {
  status: string
  explanation?: string
  original_code?: string | null
  fixed_code?: string | null
  diff?: string
  requires_review?: boolean
}

export interface BackendTest {
  test_name: string
  test_code: string
  finding_title?: string
  file?: string
  function?: string
  hypothesis?: string
  status?: string
}

export interface BackendResult {
  finding: Record<string, unknown>
  test: BackendTest
  execution: BackendExecution
  validation: BackendValidation
  fix: BackendFix
}

/** Finding as returned by the /report endpoint — extends the base Finding */
export interface BackendFinding extends Finding {
  _result?: BackendResult
}
