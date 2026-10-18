import { useMemo } from 'react'
import { Link } from 'react-router'
import { useChanges, useStatus, useSync, useTriage, useUpcoming } from '../api/client'
import { Badge, Button, Card, QueryState } from '../components/ui'
import { CATEGORY_TONE, PRIORITY_TONE, fmtDate, humanize, isPast, relative } from '../components/format'

export default function Today() {
  const upcoming = useUpcoming(7, 2)
  const urgent = useTriage({ days: 7, priorities: ['urgent'] })
  const soon = useTriage({ days: 7, priorities: ['soon'] })
  // Rounded to the hour so the query key (and cache) stays stable between renders.
  const since = useMemo(() => {
    const d = new Date(Date.now() - 3 * 86_400_000)
    d.setMinutes(0, 0, 0)
    return d.toISOString().replace(/\.\d{3}Z$/, 'Z')
  }, [])
  const changes = useChanges(since)
  const status = useStatus()
  const sync = useSync()
  const last = status.data?.sync.last as { finished_at?: string; started_at?: string } | null | undefined
  const messages = [...(urgent.data ?? []), ...(soon.data ?? [])]

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card
        title="Deadlines — next 7 days"
        actions={
          <>
            <span className="text-xs text-slate-500">
              {status.data?.sync.busy ? `${status.data.sync.busy}…` : last ? `synced ${relative(last.finished_at ?? last.started_at)}` : ''}
            </span>
            <Button disabled={!!status.data?.sync.busy || sync.isPending} onClick={() => sync.mutate()}>Sync now</Button>
          </>
        }
      >
        <QueryState q={upcoming} empty="Nothing due. 🎉">
          <ul className="space-y-2">
            {upcoming.data?.map((it) => {
              const when = it.due_at ?? it.starts_at
              const submitted = (it.data as { submitted?: boolean }).submitted
              return (
                <li key={it.id} className="flex items-start gap-2 text-sm">
                  <span className={`w-28 shrink-0 ${isPast(when) ? 'font-semibold text-red-700' : 'text-slate-600'}`}>
                    {fmtDate(when)}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <Badge>{it.kind}</Badge>
                      {submitted && <Badge tone="green">submitted</Badge>}
                      {it.url
                        ? <a className="truncate hover:underline" href={it.url} target="_blank" rel="noreferrer">{it.title}</a>
                        : <span className="truncate">{it.title}</span>}
                    </div>
                    <div className="text-xs text-slate-500">{it.course_name} · {relative(when)}</div>
                  </div>
                </li>
              )
            })}
          </ul>
        </QueryState>
      </Card>

      <Card title="Needs attention" actions={<Link className="text-sm text-sky-700 hover:underline" to="/inbox">Inbox →</Link>}>
        <QueryState q={urgent.isPending ? urgent : soon} empty="">
          {messages.length === 0 ? <p className="text-sm text-slate-500">No urgent or soon messages this week.</p> : (
            <ul className="space-y-2">
              {messages.map((r) => (
                <li key={r.id} className="text-sm">
                  <div className="flex items-center gap-1.5">
                    <Badge tone={PRIORITY_TONE[r.priority]}>{r.priority}</Badge>
                    <Badge tone={CATEGORY_TONE[r.category]}>{humanize(r.category)}</Badge>
                    <span className="truncate font-medium">{r.title}</span>
                  </div>
                  <p className="mt-0.5 text-slate-600">{r.triage.summary}</p>
                </li>
              ))}
            </ul>
          )}
        </QueryState>
      </Card>

      <Card title="Changes — last 3 days" className="lg:col-span-2">
        <QueryState q={changes} empty="No changes.">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-slate-100">
              {changes.data?.map((c) => (
                <tr key={c.id}>
                  <td className="py-1.5 pr-3 whitespace-nowrap text-slate-500">{relative(c.at)}</td>
                  <td className="pr-3">
                    <Badge tone={c.change === 'removed' ? 'red' : c.change === 'created' ? 'green' : 'blue'}>{c.change}</Badge>
                  </td>
                  <td className="pr-3"><Badge>{c.kind}</Badge></td>
                  <td className="w-full">
                    {c.title}
                    {c.fields.length > 0 && <span className="text-slate-500"> — {c.fields.join(', ')}</span>}
                    {c.fields.includes('due_at') && c.due_at && <span className="text-amber-700"> → due {fmtDate(c.due_at)}</span>}
                  </td>
                  <td className="pl-3 whitespace-nowrap text-slate-500">{c.course_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
    </div>
  )
}
