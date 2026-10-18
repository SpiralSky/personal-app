import { useState } from 'react'
import { useTasks } from '../api/client'
import type { Task } from '../api/types'
import { Badge, Card, QueryState } from '../components/ui'
import { fmtDate, isPast, relative } from '../components/format'

export default function Tasks() {
  const [days, setDays] = useState(60)
  const tasks = useTasks(days)
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-1 text-sm">
        <span className="text-slate-500">next</span>
        <select className="rounded-md border border-slate-300 bg-white px-2 py-1" value={days}
                onChange={(e) => setDays(Number(e.target.value))}>
          {[14, 30, 60, 120].map((d) => <option key={d} value={d}>{d} days</option>)}
        </select>
      </label>
      <QueryState q={tasks} empty="No upcoming assignments or quizzes.">
        <div className="grid gap-3 lg:grid-cols-2">
          {tasks.data?.map((t) => <TaskCard key={t.id} t={t} />)}
        </div>
      </QueryState>
    </div>
  )
}

function TaskCard({ t }: { t: Task }) {
  const b = t.brief
  const submitted = (t.data as { submitted?: boolean }).submitted
  return (
    <Card
      title={<>{t.url ? <a className="hover:underline" href={t.url} target="_blank" rel="noreferrer">{t.title}</a> : t.title}</>}
      actions={<>
        <Badge>{t.kind}</Badge>
        {submitted && <Badge tone="green">submitted</Badge>}
        {b && <Badge tone={b.confidence === 'high' ? 'green' : b.confidence === 'medium' ? 'amber' : 'gray'}
                     title="How much brief material was found">{b.confidence}</Badge>}
      </>}
    >
      <p className="text-xs text-slate-500">
        {t.course_name} · due <span className={isPast(t.due_at) ? 'font-semibold text-red-700' : ''}>{fmtDate(t.due_at)}</span> ({relative(t.due_at)})
        {b?.weightage && <> · {b.weightage}</>}
      </p>
      {!b ? (
        <p className="mt-2 text-sm text-slate-500">
          Not analysed yet.{t.brief_meta?.error && <span className="text-red-700"> Last error: {t.brief_meta.error}</span>}
        </p>
      ) : (
        <div className="mt-2 space-y-2 text-sm">
          <p>{b.summary}</p>
          <List title="Deliverables" items={b.deliverables} />
          <List title="Requirements" items={b.requirements} />
          {b.submission && <p><span className="font-medium">Submit:</span> {b.submission}</p>}
          {b.plan.length > 0 && (
            <details>
              <summary className="cursor-pointer font-medium">Plan ({b.plan.length} steps)</summary>
              <ol className="mt-1 list-decimal space-y-0.5 pl-5">
                {b.plan.map((s, i) => (
                  <li key={i}>
                    {s.step}
                    <span className="text-slate-500">
                      {s.target_date && ` — by ${fmtDate(s.target_date, false)}`}{s.est_hours != null && ` · ~${s.est_hours}h`}
                    </span>
                  </li>
                ))}
              </ol>
            </details>
          )}
          <List title="Open questions" items={b.open_questions} />
          {b.relevant_files.length > 0 && <p className="text-xs text-slate-500">From: {b.relevant_files.join(', ')}</p>}
          <p className="text-xs text-slate-400">{t.brief_meta?.provider} {t.brief_meta?.model} · {fmtDate(t.brief_meta?.created_at)}</p>
        </div>
      )}
    </Card>
  )
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div>
      <span className="font-medium">{title}</span>
      <ul className="list-disc pl-5">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  )
}
