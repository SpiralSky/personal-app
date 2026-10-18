import { useState } from 'react'
import {
  calendarUrl, useAnalyze, useAuth, useAuthCheck, useEval, useLlmStatus, useLogin, useStatus, useSync,
} from '../api/client'
import type { EvalPart } from '../api/types'
import { Badge, Button, Card, Json, QueryState } from '../components/ui'
import { fmtDate, relative } from '../components/format'

export default function System() {
  const status = useStatus()
  const auth = useAuth()
  const check = useAuthCheck()
  const login = useLogin()
  const sync = useSync()
  const llm = useLlmStatus()
  const analyze = useAnalyze()
  const [force, setForce] = useState(false)
  const [cutoff, setCutoff] = useState(0.8)
  const evalQ = useEval(cutoff)
  const busy = auth.data?.busy
  const pct = (x: number | null | undefined) => (x == null ? '—' : `${Math.round(x * 100)}%`)

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Brightspace" actions={<>
        <Button disabled={!!busy || check.isPending} onClick={() => check.mutate()}>Check sessions</Button>
        <Button disabled={!!busy || login.isPending} onClick={() => login.mutate()}>Sign in</Button>
        <Button disabled={!!busy || sync.isPending} onClick={() => sync.mutate()}>Sync now</Button>
      </>}>
        <QueryState q={auth}>
          {busy && <p className="mb-2 text-sm text-amber-700">Busy: {busy}…</p>}
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(auth.data?.hosts ?? {}).map(([host, h]) => (
                <tr key={host}>
                  <td className="py-1 pr-3">{host}</td>
                  <td className="pr-3"><Badge tone={h.state === 'ok' ? 'green' : h.state === 'login_required' ? 'red' : 'gray'}>{h.state}</Badge></td>
                  <td className="text-xs text-slate-500">{h.user} {h.checked_at && `· checked ${relative(h.checked_at)}`}{h.detail && ` · ${h.detail}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
        {status.data?.sync.last && (
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer">Last sync: {fmtDate((status.data.sync.last as { finished_at?: string }).finished_at)}</summary>
            <Json value={status.data.sync.last} />
          </details>
        )}
      </Card>

      <Card title="Stored items">
        <QueryState q={status}>
          <table className="w-full text-sm">
            <tbody>
              {status.data?.stats.map((s) => (
                <tr key={`${s.source}/${s.kind}`}>
                  <td className="py-0.5 pr-3 text-slate-500">{s.source}</td><td className="pr-3">{s.kind}</td>
                  <td className="text-right tabular-nums">{s.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>

      <Card title="Analysis" actions={<>
        <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} /> force</label>
        <Button disabled={status.data?.analysis.running || analyze.isPending}
                onClick={() => analyze.mutate({ triage: true, briefs: true, force })}>Run analysis</Button>
      </>}>
        <p className="text-sm">
          Auto: {status.data?.analysis.auto ? 'on' : 'off'} · {status.data?.analysis.running ? <Badge tone="amber">running</Badge> : 'idle'}
        </p>
        {status.data?.analysis.last && <details className="mt-2 text-sm"><summary className="cursor-pointer">Last run</summary><Json value={status.data.analysis.last} /></details>}
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer">LLM providers</summary>
          <QueryState q={llm}><Json value={llm.data} /></QueryState>
        </details>
      </Card>

      <Card title="Calendar feed">
        <p className="text-sm text-slate-600">Subscribe to deadlines from a calendar app on this computer:</p>
        <div className="mt-2 flex gap-2">
          <input readOnly className="flex-1 rounded-md border border-slate-300 bg-slate-50 px-2 py-1 text-sm" value={calendarUrl()} />
          <Button onClick={() => navigator.clipboard.writeText(calendarUrl())}>Copy</Button>
        </div>
      </Card>

      <Card title="Triage accuracy vs your labels" className="lg:col-span-2" actions={
        <label className="flex items-center gap-2 text-sm">
          cutoff {cutoff.toFixed(2)}
          <input type="range" min={0.5} max={0.99} step={0.01} value={cutoff} onChange={(e) => setCutoff(Number(e.target.value))} />
        </label>
      }>
        <QueryState q={evalQ}>
          <p className="mb-3 text-sm">{evalQ.data?.labelled} labelled messages. Label more in the Inbox review queue to calibrate.</p>
          <div className="grid gap-4 md:grid-cols-2">
            {(['category', 'priority'] as const).map((k) => {
              const e: EvalPart | undefined = evalQ.data?.[k]
              return e && (
                <div key={k}>
                  <h3 className="font-medium capitalize">{k}</h3>
                  <dl className="grid grid-cols-2 gap-x-3 text-sm">
                    <dt className="text-slate-500">final accuracy</dt><dd>{pct(e.final_accuracy)} (n={e.n})</dd>
                    <dt className="text-slate-500">classifier accuracy</dt><dd>{pct(e.classifier_accuracy)}</dd>
                    <dt className="text-slate-500">above cutoff</dt><dd>{pct(e.classifier_accuracy_above_cutoff)}</dd>
                    <dt className="text-slate-500">coverage above cutoff</dt><dd>{pct(e.classifier_coverage_above_cutoff)}</dd>
                  </dl>
                  <table className="mt-2 w-full text-sm">
                    <thead className="text-left text-xs text-slate-500"><tr><th>confidence</th><th>n</th><th>accuracy</th><th className="w-1/2" /></tr></thead>
                    <tbody>
                      {e.buckets.map((b) => (
                        <tr key={b.range}>
                          <td>{b.range}</td><td className="tabular-nums">{b.n}</td><td>{pct(b.accuracy)}</td>
                          <td><div className="h-2 rounded bg-slate-900" style={{ width: `${(b.accuracy ?? 0) * 100}%` }} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            })}
          </div>
        </QueryState>
      </Card>
    </div>
  )
}
