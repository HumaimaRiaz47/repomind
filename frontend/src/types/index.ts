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
  result: 'fail' | 'pass'
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
