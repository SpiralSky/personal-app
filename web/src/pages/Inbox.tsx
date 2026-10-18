import { useEffect, useRef, useState } from 'react'
import { type TriageFilters, useEval, useItem, useLabel, useTriage } from '../api/client'
import { CATEGORIES, type Category, PRIORITIES, type Priority, type TriageRow } from '../api/types'
import { Badge, Button, Card, QueryState } from '../components/ui'
import { CATEGORY_TONE, PRIORITY_TONE, cx, fmtDate, humanize, relative } from '../components/format'

const PRIORITY_KEYS = ['q', 'w', 'e', 'r'] as const

const PRESETS = [
  { label: '3d', days: 3 },
  { label: '7d', days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
  { label: '1y', days: 365 },
] as const

export default function Inbox() {
  const [filters, setFilters] = useState<TriageFilters>({
    days: 14,
    categories: [],
    priorities: [],
    kinds: [],
    needs_review: false,
    include_ignored: false
  })
  const triage = useTriage(filters)
  const rows = triage.data ?? []
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const index = Math.max(0, rows.findIndex((r) => r.id === selectedId))
  const row: TriageRow | undefined = rows[index]
  const label = useLabel()
  const evalQ = useEval(0.8)

  const set = (patch: Partial<TriageFilters>) => { setFilters((f) => ({ ...f, ...patch })); setSelectedId(null) }
  const clearAll = () => {
    setFilters({ days: 14, categories: [], priorities: [], kinds: [], needs_review: false, include_ignored: false })
    setSelectedId(null)
  }
  const go = (delta: number) => {
    const next = rows[Math.min(rows.length - 1, Math.max(0, index + delta))]
    if (next) setSelectedId(next.id)
  }

  const hasActiveFilters = (filters.categories?.length ?? 0) > 0 || (filters.priorities?.length ?? 0) > 0 ||
                          (filters.kinds?.length ?? 0) > 0 || filters.date_from || filters.date_to

  // Every label stores both fields (unchanged one = current value), so each label is a full training example.
  const apply = (r: TriageRow, patch: { category?: Category; priority?: Priority }, advance: boolean) => {
    label.mutate({ id: r.id, category: patch.category ?? r.category, priority: patch.priority ?? r.priority,
                   note: r.label_note })
    if (advance) go(1)
  }

  // Keyboard: j/k move, 1–8 category, q/w/e/r priority (advances), Enter accepts as-is (advances).
  const keyState = useRef({ row, rows, index, apply, go })
  keyState.current = { row, rows, index, apply, go }
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (e.ctrlKey || e.metaKey || e.altKey || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) return
      const { row: r, apply: ap, go: g } = keyState.current
      if (e.key === 'j' || e.key === 'ArrowDown') g(1)
      else if (e.key === 'k' || e.key === 'ArrowUp') g(-1)
      else if (!r) return
      else if (e.key >= '1' && e.key <= '8') ap(r, { category: CATEGORIES[Number(e.key) - 1] }, false)
      else if ((PRIORITY_KEYS as readonly string[]).includes(e.key))
        ap(r, { priority: PRIORITIES[PRIORITY_KEYS.indexOf(e.key as (typeof PRIORITY_KEYS)[number])] }, true)
      else if (e.key === 'Enter') ap(r, {}, true)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    document.getElementById(`row-${row?.id}`)?.scrollIntoView({ block: 'nearest' })
  }, [row?.id])

  const labelledHere = rows.filter((r) => r.corrected).length

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant={filters.needs_review ? 'primary' : 'default'}
          onClick={() => set({ needs_review: !filters.needs_review })}
        >
          Review queue
        </Button>

        <FilterDropdown
          label="Category"
          options={CATEGORIES}
          selected={filters.categories ?? []}
          onChange={(v) => set({ categories: v })}
          formatLabel={humanize}
        />

        <FilterDropdown
          label="Priority"
          options={PRIORITIES}
          selected={filters.priorities ?? []}
          onChange={(v) => set({ priorities: v })}
          formatLabel={(p) => p}
        />

        <FilterDropdown
          label="Kind"
          options={['email', 'announcement'] as const}
          selected={filters.kinds ?? []}
          onChange={(v) => set({ kinds: v })}
          formatLabel={humanize}
        />

        <DateRangeFilter
          days={filters.days}
          dateFrom={filters.date_from}
          dateTo={filters.date_to}
          onChange={(range) => set(range)}
        />

        <label className="flex items-center gap-1 text-sm">
          <input type="checkbox" checked={!!filters.include_ignored}
                 onChange={(e) => set({ include_ignored: e.target.checked })} />
          include ignored
        </label>

        {hasActiveFilters && (
          <Button variant="ghost" onClick={clearAll} className="text-xs">
            Clear all
          </Button>
        )}

        <span className="ml-auto text-sm text-slate-500">
          {labelledHere}/{rows.length} labelled here · {evalQ.data?.labelled ?? '…'} total
        </span>
      </div>

      {hasActiveFilters && (
        <div className="flex flex-wrap gap-1.5">
          {(filters.categories ?? []).map((c) => (
            <FilterChip key={c} onRemove={() => set({ categories: filters.categories?.filter(x => x !== c) })}>
              {humanize(c)}
            </FilterChip>
          ))}
          {(filters.priorities ?? []).map((p) => (
            <FilterChip key={p} onRemove={() => set({ priorities: filters.priorities?.filter(x => x !== p) })}>
              {p}
            </FilterChip>
          ))}
          {(filters.kinds ?? []).map((k) => (
            <FilterChip key={k} onRemove={() => set({ kinds: filters.kinds?.filter(x => x !== k) })}>
              {humanize(k)}
            </FilterChip>
          ))}
          {(filters.date_from || filters.date_to) && (
            <FilterChip onRemove={() => set({ date_from: undefined, date_to: undefined, days: 14 })}>
              {filters.date_from && filters.date_to
                ? `${filters.date_from} to ${filters.date_to}`
                : filters.date_from
                ? `From ${filters.date_from}`
                : `Until ${filters.date_to}`}
            </FilterChip>
          )}
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card className="max-h-[calc(100vh-9rem)] overflow-auto">
          <QueryState q={triage} empty="Nothing here.">
            <ul className="-m-4 divide-y divide-slate-100">
              {rows.map((r) => (
                <li key={r.id} id={`row-${r.id}`}>
                  <button
                    onClick={() => setSelectedId(r.id)}
                    className={cx('block w-full px-4 py-2 text-left', r.id === row?.id ? 'bg-sky-50' : 'hover:bg-slate-50')}
                  >
                    <div className="flex items-center gap-1.5">
                      {r.needs_review && <span title="needs review" className="h-2 w-2 shrink-0 rounded-full bg-amber-500" />}
                      {r.corrected && <span title="labelled by you" className="text-xs text-emerald-600">✓</span>}
                      <span className="truncate text-sm font-medium">{r.title || '(no subject)'}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
                      <Badge tone={CATEGORY_TONE[r.category]}>{humanize(r.category)}</Badge>
                      <Badge tone={PRIORITY_TONE[r.priority]}>{r.priority}</Badge>
                      <span className="truncate">{r.sender ?? r.course_name}</span>
                      <span className="ml-auto shrink-0">{relative(r.occurred_at)}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </QueryState>
        </Card>
        {row ? <Detail row={row} onLabel={apply} saving={label.isPending} /> : null}
      </div>
    </div>
  )
}

function FilterDropdown<T extends string>({ label, options, selected, onChange, formatLabel }: {
  label: string
  options: readonly T[]
  selected: T[]
  onChange: (value: T[]) => void
  formatLabel: (value: T) => string
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [])

  const toggle = (value: T) => {
    onChange(selected.includes(value) ? selected.filter(v => v !== value) : [...selected, value])
  }

  return (
    <div ref={ref} className="relative">
      <Button
        variant="default"
        onClick={() => setOpen(!open)}
        className={cx('text-sm', selected.length > 0 && 'ring-2 ring-sky-500')}
      >
        {label}
        {selected.length > 0 && <Badge tone="blue">{selected.length}</Badge>}
      </Button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-10 min-w-[200px] rounded-lg border border-slate-200 bg-white shadow-lg p-2">
          <div className="space-y-1">
            {options.map((opt) => (
              <label key={opt} className="flex items-center gap-2 px-2 py-1.5 hover:bg-slate-50 rounded cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.includes(opt)}
                  onChange={() => toggle(opt)}
                  className="rounded border-slate-300"
                />
                <span className="text-sm">{formatLabel(opt)}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function DateRangeFilter({ days, dateFrom, dateTo, onChange }: {
  days?: number
  dateFrom?: string
  dateTo?: string
  onChange: (range: { days?: number; date_from?: string; date_to?: string }) => void
}) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'preset' | 'custom'>(dateFrom || dateTo ? 'custom' : 'preset')
  const [customFrom, setCustomFrom] = useState(dateFrom ?? '')
  const [customTo, setCustomTo] = useState(dateTo ?? '')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [])

  const selectPreset = (d: number) => {
    onChange({ days: d, date_from: undefined, date_to: undefined })
    setMode('preset')
    setOpen(false)
  }

  const applyCustom = () => {
    onChange({ days: undefined, date_from: customFrom || undefined, date_to: customTo || undefined })
    setOpen(false)
  }

  const isCustom = dateFrom || dateTo
  const activeLabel = isCustom
    ? (dateFrom && dateTo ? `${dateFrom} to ${dateTo}` : dateFrom ? `From ${dateFrom}` : `Until ${dateTo}`)
    : `${days}d`

  return (
    <div ref={ref} className="relative">
      <Button
        variant="default"
        onClick={() => setOpen(!open)}
        className={cx('text-sm', isCustom && 'ring-2 ring-sky-500')}
      >
        {activeLabel}
      </Button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-10 min-w-[280px] rounded-lg border border-slate-200 bg-white shadow-lg p-3">
          <div className="flex gap-2 mb-3 border-b border-slate-100 pb-2">
            <button
              onClick={() => setMode('preset')}
              className={cx('px-2 py-1 text-sm rounded', mode === 'preset' ? 'bg-slate-900 text-white' : 'hover:bg-slate-100')}
            >
              Preset
            </button>
            <button
              onClick={() => setMode('custom')}
              className={cx('px-2 py-1 text-sm rounded', mode === 'custom' ? 'bg-slate-900 text-white' : 'hover:bg-slate-100')}
            >
              Custom
            </button>
          </div>

          {mode === 'preset' ? (
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => selectPreset(p.days)}
                  className={cx(
                    'px-3 py-1.5 text-sm rounded-md border',
                    days === p.days && !isCustom
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 bg-white hover:bg-slate-50'
                  )}
                >
                  {p.label}
                </button>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              <label className="block">
                <span className="text-xs text-slate-500">From</span>
                <input
                  type="date"
                  value={customFrom}
                  onChange={(e) => setCustomFrom(e.target.value)}
                  className="w-full mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500">To</span>
                <input
                  type="date"
                  value={customTo}
                  onChange={(e) => setCustomTo(e.target.value)}
                  className="w-full mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                />
              </label>
              <Button onClick={applyCustom} className="w-full">
                Apply
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FilterChip({ children, onRemove }: { children: React.ReactNode; onRemove: () => void }) {
  return (
    <div className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-sky-100 text-sky-900 rounded-full">
      {children}
      <button onClick={onRemove} className="hover:text-sky-700" title="Remove filter">
        ×
      </button>
    </div>
  )
}

function Detail({ row, onLabel, saving }: {
  row: TriageRow
  onLabel: (r: TriageRow, patch: { category?: Category; priority?: Priority }, advance: boolean) => void
  saving: boolean
}) {
  const item = useItem(row.id)
  const t = row.triage
  const clf = t.classification
  const label = useLabel()
  const [note, setNote] = useState(row.label_note ?? '')
  useEffect(() => setNote(row.label_note ?? ''), [row.id, row.label_note])

  return (
    <div className="space-y-3">
      <Card
        title={row.title || '(no subject)'}
        actions={row.url && <a className="text-sm text-sky-700 hover:underline" href={row.url} target="_blank" rel="noreferrer">open ↗</a>}
      >
        <p className="text-xs text-slate-500">
          {row.sender ?? row.course_name} · {fmtDate(row.occurred_at)} · {row.kind} · by {row.decided_by ?? row.provider}
          {row.model ? ` (${row.model})` : ''}
        </p>
        <p className="mt-2">{t.summary}</p>

        {t.actions.length > 0 && (
          <Section title="Actions">
            {t.actions.map((a, i) => <li key={i}>{a.what}{a.due && <span className="text-slate-500"> — {fmtDate(a.due)}</span>}</li>)}
          </Section>
        )}
        {t.dates.length > 0 && (
          <Section title="Dates">
            {t.dates.map((d, i) => <li key={i}><Badge>{d.kind}</Badge> {d.what} — {fmtDate(d.when)}</li>)}
          </Section>
        )}
        {t.opportunity && (
          <Section title="Opportunity">
            <li>
              <Badge tone="green">{t.opportunity.kind}</Badge> {t.opportunity.title}
              {t.opportunity.deadline && <> · apply by {fmtDate(t.opportunity.deadline)}</>}
              {t.opportunity.eligibility && <> · {t.opportunity.eligibility}</>}
              {t.opportunity.cost && <> · {t.opportunity.cost}</>}
            </li>
          </Section>
        )}
        {t.links.length > 0 && (
          <Section title="Links">
            {t.links.map((l, i) => <li key={i}><a className="text-sky-700 hover:underline" href={l.url} target="_blank" rel="noreferrer">{l.label}</a></li>)}
          </Section>
        )}
      </Card>

      <Card title="Label" actions={saving && <span className="text-xs text-slate-500">saving…</span>}>
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {CATEGORIES.map((c, i) => (
              <Choice key={c} active={row.category === c} model={t.category === c} p={clf?.category?.label === c ? clf.category.p : undefined}
                      onClick={() => onLabel(row, { category: c }, false)}>
                <kbd className="text-slate-400">{i + 1}</kbd> {humanize(c)}
              </Choice>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {PRIORITIES.map((p, i) => (
              <Choice key={p} active={row.priority === p} model={t.priority === p} p={clf?.priority?.label === p ? clf.priority.p : undefined}
                      onClick={() => onLabel(row, { priority: p }, true)}>
                <kbd className="text-slate-400">{PRIORITY_KEYS[i]}</kbd> {p}
              </Choice>
            ))}
            <Button className="ml-auto" onClick={() => onLabel(row, {}, true)} title="Accept the current values (Enter)">
              ✓ Accept <kbd className="text-slate-400">↵</kbd>
            </Button>
          </div>
          <div className="flex gap-2">
            <input className="flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="note (optional)"
                   value={note} onChange={(e) => setNote(e.target.value)} />
            <Button disabled={note === (row.label_note ?? '')}
                    onClick={() => label.mutate({ id: row.id, category: row.category, priority: row.priority, note: note || null })}>
              Save note
            </Button>
          </div>
          <p className="text-xs text-slate-500">
            Dashed = model's answer{clf ? ' (with classifier confidence)' : ''}. Keys: j/k move · 1–8 category · q/w/e/r priority (next) · Enter accept (next).
          </p>
        </div>
      </Card>

      <Card title="Message">
        <QueryState q={item}>
          <pre className="max-h-[50vh] overflow-auto text-sm whitespace-pre-wrap font-sans">{item.data?.body || '(empty)'}</pre>
        </QueryState>
      </Card>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-3">
      <h3 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h3>
      <ul className="mt-1 space-y-1 text-sm">{children}</ul>
    </div>
  )
}

function Choice({ active, model, p, onClick, children }: {
  active: boolean; model: boolean; p?: number; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={cx(
        'rounded-md border px-2 py-1 text-sm',
        active ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-300 bg-white hover:bg-slate-100',
        model && !active && 'border-dashed border-slate-500',
      )}
    >
      {children}{p !== undefined && <span className="ml-1 text-xs opacity-70">{p.toFixed(2)}</span>}
    </button>
  )
}
