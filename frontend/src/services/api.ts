import type {
  AnalysisReport,
  BackendFinding,
  BackendResult,
  Finding,
  FixSuggestion,
  PipelineStageId,
  TestEvidence,
} from '../types'

// -----------------------------------------------------------------------------
// GitHub URL validation
// -----------------------------------------------------------------------------

const GITHUB_URL_RE =
  /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/

export function validateRepoUrl(url: string): string | null {
  const trimmed = url.trim()

  if (!trimmed) {
    return 'Enter a GitHub repository URL.'
  }

  if (!GITHUB_URL_RE.test(trimmed)) {
    return 'Enter a valid URL like https://github.com/owner/repo'
  }

  return null
}

// -----------------------------------------------------------------------------
// Generic API helper
// -----------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  body: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let message = `Backend error (HTTP ${response.status})`

    try {
      const data = await response.json()

      if (data?.detail) {
        message = String(data.detail)
      }
    } catch {
      // Keep generic message.
    }

    throw new Error(message)
  }

  return response.json() as Promise<T>
}

// -----------------------------------------------------------------------------
// Pipeline stages
// -----------------------------------------------------------------------------

const STAGE_ORDER: PipelineStageId[] = [
  'ingestion',
  'orchestrator',
  'repo_analyzer',
  'bug_hunter',
  'test_generation',
  'validation',
]

const STAGE_TICK_MS = 700

// -----------------------------------------------------------------------------
// Main repository analysis
// -----------------------------------------------------------------------------

export async function runAnalysis(
  url: string,
  onStage: (stageId: PipelineStageId) => void,
): Promise<AnalysisReport> {
  let stageIndex = 0

  const ticker = window.setInterval(() => {
    if (stageIndex < STAGE_ORDER.length) {
      onStage(STAGE_ORDER[stageIndex])
      stageIndex += 1
    }
  }, STAGE_TICK_MS)

  try {
    return await apiFetch<AnalysisReport>(
      '/api/repositories/report',
      {
        repo_url: url,
      },
    )
  } finally {
    window.clearInterval(ticker)
  }
}

// -----------------------------------------------------------------------------
// Evidence
// -----------------------------------------------------------------------------

export function fetchEvidence(
  finding: Finding,
): Promise<TestEvidence> {
  const backendFinding = finding as BackendFinding

  const result = backendFinding._result as
    | BackendResult
    | undefined

  const testCode = result?.test?.test_code ?? ''
  const execution = result?.execution
  const validation = result?.validation

  let testResult: TestEvidence['result']

  // Validation is authoritative.
  if (validation?.status === 'test_generation_error') {
    testResult = 'error'
  } else if (validation?.status === 'needs_review') {
    testResult = 'needs_review'
  } else {
    switch (execution?.status) {
      case 'failed':
        testResult = 'fail'
        break

      case 'passed':
        testResult = 'pass'
        break

      case 'skipped':
        testResult = 'skipped'
        break

      case 'error':
        testResult = 'error'
        break

      case 'timeout':
        testResult = 'needs_review'
        break

      default:
        testResult = 'error'
        break
    }
  }

  const output = [
    execution?.stdout ?? '',
    execution?.stderr ?? '',
  ]
    .filter(Boolean)
    .join('\n')
    .trim()

  return Promise.resolve({
    findingId: finding.id,
    testCode,
    testFramework: 'pytest',
    result: testResult,
    output,
    reasoning:
      validation?.reason ??
      'No reasoning available.',
  })
}

// -----------------------------------------------------------------------------
// Fix
// -----------------------------------------------------------------------------

export function fetchFix(
  finding: Finding,
): Promise<FixSuggestion> {
  const backendFinding = finding as BackendFinding

  const result = backendFinding._result as
    | BackendResult
    | undefined

  const backendFix = result?.fix

  /*
   * The backend performs the fix during the analysis pipeline.
   *
   * Successful backend state:
   *     fix_verified
   *
   * Other states include:
   *     proposed
   *     fix_failed
   *     regression_failed
   *     no_regression_tests
   *     not_applicable
   *
   * We deliberately do NOT treat every fix as successful.
   */

  const fixStatus = backendFix?.status ?? 'not_applicable'

  const isVerified = fixStatus === 'fix_verified'

  /*
   * Current BackendFix exposes the fix itself but not a standardized
   * regression-test count. Therefore we don't invent a fake 0/0 result.
   *
   * For a verified fix, the backend contract guarantees that regression
   * validation succeeded and at least one regression test passed.
   *
   * The UI will display this as "Regression suite verified".
   */
  const regressionTests = isVerified
    ? {
        total: 1,
        passed: 1,
      }
    : {
        total: 0,
        passed: 0,
      }

  return Promise.resolve({
    findingId: finding.id,

    explanation:
      backendFix?.explanation ??
      (
        isVerified
          ? 'The fix was applied and verified by the regression suite.'
          : `Fix status: ${fixStatus}.`
      ),

    diff: {
      file: finding.file,
      before: backendFix?.original_code ?? '',
      after: backendFix?.fixed_code ?? '',
    },

    regressionTests,

    applied: isVerified,
  })
}

// -----------------------------------------------------------------------------
// Apply fix
// -----------------------------------------------------------------------------

export function applyFix(
  findingId: string,
): Promise<FixSuggestion> {
  /*
   * IMPORTANT:
   *
   * The backend pipeline already performs the patch application.
   * There is currently no separate frontend apply endpoint.
   *
   * Therefore this function must NOT fabricate a successful fix.
   *
   * The real FixSuggestion is already obtained through fetchFix().
   * The hook will use that result instead of replacing it with fake data.
   */

  return Promise.resolve({
    findingId,

    explanation:
      'The fix result was already produced by the backend analysis pipeline.',

    diff: {
      file: '',
      before: '',
      after: '',
    },

    regressionTests: {
      total: 0,
      passed: 0,
    },

    applied: false,
  })
}