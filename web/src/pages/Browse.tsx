import { useEffect, useState } from 'react'
import { type ItemFilters, PAGE, fileUrl, useCourses, useHistory, useItem, useItems } from '../api/client'
import { Badge, Button, Card, Json, QueryState } from '../components/ui'
import { cx, fmtDate } from '../components/format'

const SOURCES = ['brightspace:splms', 'brightspace:lms', 'outlook'] as const
const KINDS = ['assignment', 'quiz', 'announcement', 'content', 'event', 'grade', 'course', 'email'] as const

export default function Browse() {
  const [text, setText] = useState('')
  const [f, setF] = useState<ItemFilters>({ offset: 0 })
  const items = useItems(f)
  const courses = useCourses()
  const [selected, setSelected] = useState<string | null>(null)

  // Debounce the search box.
  useEffect(() => {
    const t = setTimeout(() => setF((p) => (p.q === (text || undefined) ? p : { ...p, q: text || undefined, offset: 0 })), 300)
    return () => clearTimeout(t)
  }, [text])

  const set = (patch: Partial<ItemFilters>) => setF((p) => ({ ...p, ...patch, offset: 0 }))
  const offset = f.offset ?? 0
  const sel = 'rounded-md border border-slate-300 bg-white px-2 py-1 text-sm'

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input className="w-64 rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Search title/body…"
               value={text} onChange={(e) => setText(e.target.value)} />
        <select className={sel} value={f.source ?? ''} onChange={(e) => set({ source: e.target.value || undefined })}>
          <option value="">all sources</option>
          {SOURCES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select className={sel} value={f.kind ?? ''} onChange={(e) => set({ kind: e.target.value || undefined })}>
          <option value="">all kinds</option>
          {KINDS.map((k) => <option key={k}>{k}</option>)}
        </select>
        <select className={cx(sel, 'max-w-72')} value={f.course_id ?? ''} onChange={(e) => set({ course_id: e.target.value || undefined })}>
          <option value="">all courses</option>
          {courses.data?.map((c) => <option key={c.id} value={c.course_id ?? c.external_id}>{c.title}</option>)}
        </select>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card>
          <QueryState q={items} empty="No items.">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500">
                <tr><th className="pb-2">Title</th><th>Kind</th><th>Course</th><th>Date</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.data?.map((it) => (
                  <tr key={it.id} onClick={() => setSelected(it.id)}
                      className={cx('cursor-pointer', selected === it.id ? 'bg-sky-50' : 'hover:bg-slate-50')}>
                    <td className="max-w-0 truncate py-1.5 pr-2" title={it.title}>{it.title || '(untitled)'}</td>
                    <td className="pr-2"><Badge>{it.kind}</Badge></td>
                    <td className="max-w-40 truncate pr-2 text-slate-500">{it.course_name}</td>
                    <td className="whitespace-nowrap text-slate-500">{fmtDate(it.due_at ?? it.occurred_at ?? it.first_seen, false)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 flex items-center gap-2">
              <Button disabled={offset === 0} onClick={() => setF({ ...f, offset: Math.max(0, offset - PAGE) })}>← Prev</Button>
              <span className="text-sm text-slate-500">{offset + 1}–{offset + (items.data?.length ?? 0)}</span>
              <Button disabled={(items.data?.length ?? 0) < PAGE} onClick={() => setF({ ...f, offset: offset + PAGE })}>Next →</Button>
            </div>
          </QueryState>
        </Card>
        {selected && <ItemPanel id={selected} />}
      </div>
    </div>
  )
}

function ItemPanel({ id }: { id: string }) {
  const item = useItem(id)
  const history = useHistory(id)
  const it = item.data
  return (
    <Card title={it?.title ?? id} actions={it?.url && <a className="text-sm text-sky-700 hover:underline" href={it.url} target="_blank" rel="noreferrer">open ↗</a>}>
      <QueryState q={item}>
        {it && (
          <div className="space-y-3 text-sm">
            <p className="text-xs text-slate-500">
              {it.source} · {it.kind} · {it.course_name}
              {it.due_at && <> · due {fmtDate(it.due_at)}</>}
              {it.occurred_at && <> · {fmtDate(it.occurred_at)}</>}
            </p>
            {it.file && (
              <a className="text-sky-700 hover:underline" href={fileUrl(id)} target="_blank" rel="noreferrer">📄 {it.file.filename}</a>
            )}
            {it.body && <pre className="max-h-80 overflow-auto font-sans whitespace-pre-wrap">{it.body}</pre>}
            {Object.entries(it.analyses).map(([task, a]) => (
              <details key={task}>
                <summary className="cursor-pointer font-medium">Analysis: {task} <span className="text-xs text-slate-500">({a.provider})</span></summary>
                {a.error ? <p className="text-red-700">{a.error}</p> : <Json value={a.result} />}
              </details>
            ))}
            <details>
              <summary className="cursor-pointer font-medium">Data</summary>
              <Json value={it.data} />
            </details>
            <details>
              <summary className="cursor-pointer font-medium">History ({history.data?.length ?? '…'})</summary>
              <ul className="space-y-1">
                {history.data?.map((h) => (
                  <li key={h.replaced_at}>
                    <details>
                      <summary className="cursor-pointer text-slate-600">replaced {fmtDate(h.replaced_at)}</summary>
                      <Json value={safeParse(h.snapshot)} />
                    </details>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        )}
      </QueryState>
    </Card>
  )
}

function safeParse(s: string): unknown {
  try { return JSON.parse(s) } catch { return s }
}
