interface CodeBlockProps {
  code: string
  language?: string
  tone?: 'default' | 'diff-before' | 'diff-after'
}

const TONE_STYLE: Record<NonNullable<CodeBlockProps['tone']>, string> = {
  default: 'bg-slate-900 text-slate-100',
  'diff-before': 'bg-danger-50 text-danger-900 border border-danger-200',
  'diff-after': 'bg-ok-50 text-ok-900 border border-ok-500/30',
}

export function CodeBlock({ code, language = 'python', tone = 'default' }: CodeBlockProps) {
  return (
    <pre
      className={[
        'scroll-thin overflow-x-auto rounded-xl p-3.5 text-xs leading-relaxed',
        TONE_STYLE[tone],
      ].join(' ')}
    >
      <code className="font-mono" data-language={language}>
        {code}
      </code>
    </pre>
  )
}
