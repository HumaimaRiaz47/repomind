import type { Finding, FixSuggestion, PipelineStage, RepoMeta, TestEvidence } from '../types'

export const initialStages: PipelineStage[] = [
  {
    id: 'ingestion',
    label: 'Repository Ingestion',
    description: 'Clone repository, analyze structure, identify language, dependencies, and existing tests',
    status: 'pending',
  },
  {
    id: 'orchestrator',
    label: 'Orchestrator',
    description: 'Coordinate AI agents and manage workflow',
    status: 'pending',
  },
  {
    id: 'repo_analyzer',
    label: 'Repository Analyzer',
    description: 'Understand codebase structure',
    status: 'pending',
  },
  {
    id: 'bug_hunter',
    label: 'Bug Hunter Agent',
    description: 'Find potential issues',
    status: 'pending',
  },
  {
    id: 'test_generation',
    label: 'Test Generation Agent',
    description: 'Generate test cases',
    status: 'pending',
  },
  {
    id: 'validation',
    label: 'Validation Agent',
    description: 'Run tests and verify findings',
    status: 'pending',
  },
]

export function mockRepoMeta(url: string): RepoMeta {
  const clean = url.replace(/\/$/, '')
  const parts = clean.split('/')
  const name = parts.at(-1) || 'repository'
  const owner = parts.at(-2) || 'unknown'
  return {
    url,
    owner,
    name,
    language: 'Python',
    filesScanned: 128,
    dependencies: 24,
  }
}

export const mockFindings: Finding[] = [
  {
    id: 'f1',
    title: 'Off-by-one error in pagination offset',
    description:
      'The `page * limit` calculation does not subtract 1, causing the first item of every page to be skipped.',
    severity: 'high',
    file: 'app/services/pagination.py',
    line: 42,
    agent: 'Bug Hunter Agent',
    status: 'pending',
  },
  {
    id: 'f2',
    title: 'Unhandled None from optional API field',
    description:
      '`user.profile.avatar_url` is accessed without a None check; the field is optional per the schema.',
    severity: 'medium',
    file: 'app/api/users.py',
    line: 118,
    agent: 'Bug Hunter Agent',
    status: 'pending',
  },
  {
    id: 'f3',
    title: 'Race condition on cache invalidation',
    description:
      'Cache is invalidated before the DB write commits, allowing a stale read to repopulate it.',
    severity: 'high',
    file: 'app/cache/invalidation.py',
    line: 76,
    agent: 'Bug Hunter Agent',
    status: 'pending',
  },
  {
    id: 'f4',
    title: 'Inconsistent timezone handling',
    description:
      '`datetime.now()` is used instead of `datetime.now(timezone.utc)`, causing naive datetimes to leak into comparisons.',
    severity: 'low',
    file: 'app/utils/dates.py',
    line: 15,
    agent: 'Bug Hunter Agent',
    status: 'pending',
  },
]

export const mockEvidence: Record<string, TestEvidence> = {
  f1: {
    findingId: 'f1',
    testFramework: 'pytest',
    result: 'fail',
    testCode: `def test_pagination_offset_includes_first_item():
    items = list(range(20))
    page_1 = paginate(items, page=1, limit=5)

    # First page should start at index 0, not 5
    assert page_1[0] == 0`,
    output: `FAILED tests/test_pagination.py::test_pagination_offset_includes_first_item
AssertionError: assert 5 == 0
1 failed, 0 passed in 0.04s`,
    reasoning:
      'The generated test reproduces the bug: item 0 is skipped on page 1 because the offset formula is `page * limit` instead of `(page - 1) * limit`. This confirms the finding is a real, validated issue.',
  },
  f2: {
    findingId: 'f2',
    testFramework: 'pytest',
    result: 'fail',
    testCode: `def test_avatar_url_handles_missing_profile_field():
    user = make_user(profile={"avatar_url": None})
    response = serialize_user(user)

    assert response["avatar_url"] is None  # should not raise`,
    output: `FAILED tests/test_users.py::test_avatar_url_handles_missing_profile_field
AttributeError: 'NoneType' object has no attribute 'avatar_url'
1 failed, 0 passed in 0.03s`,
    reasoning:
      'Confirmed: serialize_user raises AttributeError when avatar_url is None instead of returning null, matching the reported finding.',
  },
  f3: {
    findingId: 'f3',
    testFramework: 'pytest',
    result: 'fail',
    testCode: `def test_cache_not_stale_after_concurrent_write():
    write_record(id=1, value="new")
    invalidate_then_read = simulate_concurrent_read(id=1)

    assert invalidate_then_read == "new"`,
    output: `FAILED tests/test_cache.py::test_cache_not_stale_after_concurrent_write
AssertionError: assert 'old' == 'new'
1 failed, 0 passed in 0.11s`,
    reasoning:
      'The test reproduces a stale read: cache invalidation fires before the DB commit, so a concurrent read repopulates the cache with the old value.',
  },
  f4: {
    findingId: 'f4',
    testFramework: 'pytest',
    result: 'pass',
    testCode: `def test_now_is_timezone_aware():
    ts = get_current_timestamp()
    assert ts.tzinfo is not None`,
    output: `PASSED tests/test_dates.py::test_now_is_timezone_aware
1 passed in 0.02s`,
    reasoning:
      'The generated test passed against current code, meaning it could not reproduce a failure. Treated as a false positive and rejected rather than pursued for a fix.',
  },
}

export const mockFixes: Record<string, FixSuggestion> = {
  f1: {
    findingId: 'f1',
    explanation:
      'Adjust the offset formula so page 1 starts at index 0. Also add a regression test to lock in the fix.',
    diff: {
      file: 'app/services/pagination.py',
      before: `def paginate(items, page, limit):
    start = page * limit
    return items[start:start + limit]`,
      after: `def paginate(items, page, limit):
    start = (page - 1) * limit
    return items[start:start + limit]`,
    },
    regressionTests: { total: 12, passed: 12 },
    applied: false,
  },
  f2: {
    findingId: 'f2',
    explanation:
      'Guard the optional `profile` field before accessing `avatar_url`, defaulting to None to match the schema contract.',
    diff: {
      file: 'app/api/users.py',
      before: `def serialize_user(user):
    return {
        "id": user.id,
        "avatar_url": user.profile.avatar_url,
    }`,
      after: `def serialize_user(user):
    return {
        "id": user.id,
        "avatar_url": user.profile.avatar_url if user.profile else None,
    }`,
    },
    regressionTests: { total: 9, passed: 9 },
    applied: false,
  },
  f3: {
    findingId: 'f3',
    explanation:
      'Reorder operations so cache invalidation happens after the DB commit resolves, closing the race window.',
    diff: {
      file: 'app/cache/invalidation.py',
      before: `def update_record(record):
    cache.invalidate(record.id)
    db.commit(record)`,
      after: `def update_record(record):
    db.commit(record)
    cache.invalidate(record.id)`,
    },
    regressionTests: { total: 15, passed: 15 },
    applied: false,
  },
}
