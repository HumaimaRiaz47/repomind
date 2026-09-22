import { ArrowRight, FolderGit2, Link2, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { validateRepoUrl } from '../services/api'

interface RepositoryInputProps {
  onSubmit: (url: string) => void
  isSubmitting: boolean
}

const EXAMPLES = ['https://github.com/pallets/flask', 'https://github.com/psf/requests']

export function RepositoryInput({ onSubmit, isSubmitting }: RepositoryInputProps) {
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const validationError = validateRepoUrl(url)
    if (validationError) {
      setError(validationError)
      return
    }
    setError(null)
    onSubmit(url.trim())
  }

  return (
    <div className="mx-auto w-full max-w-xl">
      <div className="rounded-2xl border border-brand-100 bg-white/80 p-8 shadow-xl shadow-brand-900/5 backdrop-blur">
        <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          <FolderGit2 className="h-6 w-6" strokeWidth={2} />
        </div>
        <h2 className="text-center text-xl font-semibold text-slate-900">Enter GitHub Repository URL</h2>
        <p className="mt-1 text-center text-sm text-slate-500">
          RepoMind will clone the repo, scan it, and hunt for validated bugs.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
          <label htmlFor="repo-url" className="sr-only">
            GitHub repository URL
          </label>
          <div
            className={[
              'flex items-center gap-2 rounded-xl border bg-white px-3.5 py-2.5 transition-colors focus-within:ring-2',
              error ? 'border-danger-500 focus-within:ring-danger-100' : 'border-slate-200 focus-within:border-brand-400 focus-within:ring-brand-100',
            ].join(' ')}
          >
            <Link2 className="h-4 w-4 shrink-0 text-slate-400" />
            <input
              id="repo-url"
              type="text"
              inputMode="url"
              autoComplete="off"
              placeholder="https://github.com/owner/repo"
              value={url}
              disabled={isSubmitting}
              onChange={(e) => {
                setUrl(e.target.value)
                if (error) setError(null)
              }}
              className="w-full bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none disabled:opacity-60"
            />
          </div>
          {error && <p className="text-xs font-medium text-danger-600">{error}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="group mt-1 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand-600 to-brand-700 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 transition-all hover:shadow-brand-600/35 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing…
              </>
            ) : (
              <>
                Analyze Repository
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </>
            )}
          </button>
        </form>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-xs text-slate-400">
          <span>Try:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              disabled={isSubmitting}
              onClick={() => setUrl(ex)}
              className="rounded-full border border-slate-200 px-2.5 py-1 font-medium text-slate-500 transition-colors hover:border-brand-300 hover:text-brand-600 disabled:opacity-60"
            >
              {ex.replace('https://github.com/', '')}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
