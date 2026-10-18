import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { TONES, type Tone, cx, humanize } from './format'

// ── Components ───────────────────────────────────────────────────────────────

export function Badge({ tone = 'gray', children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={cx('inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium whitespace-nowrap', TONES[tone])}>
      {children}
    </span>
  )
}

export function Button({ variant = 'default', className, ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' | 'ghost' }) {
  return (
    <button
      {...props}
      className={cx(
        'inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed',
        variant === 'primary' && 'bg-slate-900 text-white hover:bg-slate-700',
        variant === 'default' && 'border border-slate-300 bg-white hover:bg-slate-100',
        variant === 'ghost' && 'hover:bg-slate-100',
        className,
      )}
    />
  )
}

export function Card({ title, actions, children, className }:
  { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx('rounded-lg border border-slate-200 bg-white', className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-2.5">
          <h2 className="text-sm font-semibold">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function QueryState({ q, empty, children }: {
  q: { isPending: boolean; error: Error | null; data?: unknown }
  empty?: string
  children: ReactNode
}) {
  if (q.isPending) return <p className="text-sm text-slate-500">Loading…</p>
  if (q.error) return <p className="text-sm text-red-700">Error: {q.error.message}</p>
  if (empty && Array.isArray(q.data) && q.data.length === 0) return <p className="text-sm text-slate-500">{empty}</p>
  return <>{children}</>
}

export function Select<T extends string>({ value, onChange, options, label }: {
  value: T | ''
  onChange: (v: T | '') => void
  options: readonly T[]
  label: string
}) {
  return (
    <label className="flex items-center gap-1 text-sm">
      <span className="text-slate-500">{label}</span>
      <select
        className="rounded-md border border-slate-300 bg-white px-2 py-1"
        value={value}
        onChange={(e) => onChange(e.target.value as T | '')}
      >
        <option value="">any</option>
        {options.map((o) => <option key={o} value={o}>{humanize(o)}</option>)}
      </select>
    </label>
  )
}

export function Json({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(value, null, 2)}</pre>
  )
}
