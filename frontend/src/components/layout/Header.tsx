import { Brain } from 'lucide-react'

export function Header() {
  return (
    <header className="flex flex-col items-center gap-1 pt-10 pb-6 text-center">
      <div className="flex items-center gap-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-lg shadow-brand-600/20">
          <Brain className="h-6 w-6" strokeWidth={2.25} />
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">RepoMind</h1>
      </div>
      <p className="text-sm font-medium text-brand-600">Ask Before You Break</p>
    </header>
  )
}
