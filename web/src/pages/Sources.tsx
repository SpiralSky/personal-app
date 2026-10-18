import { useAuth, useAuthCheck, useLogin, useStatus, useSync } from '../api/client'
import { Badge, Button, Card, QueryState } from '../components/ui'
import { fmtDate, relative } from '../components/format'

export default function Sources() {
  const auth = useAuth()
  const status = useStatus()
  const check = useAuthCheck()
  const login = useLogin()
  const sync = useSync()
  const busy = auth.data?.busy

  const mailStats = status.data?.stats.filter((s) => s.source === 'outlook') ?? []
  const mailCount = mailStats.reduce((n, s) => n + s.n, 0)

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
                  <td className="py-1 pr-3 font-medium">{host}</td>
                  <td className="pr-3">
                    <Badge tone={h.state === 'ok' ? 'green' : h.state === 'login_required' ? 'red' : 'gray'}>
                      {h.state === 'ok' ? 'Signed in' : h.state === 'login_required' ? 'Sign-in required' : h.state}
                    </Badge>
                  </td>
                  <td className="text-xs text-slate-500">
                    {h.user && <span>{h.user}</span>}
                    {h.checked_at && <span> · checked {relative(h.checked_at)}</span>}
                    {h.detail && <span> · {h.detail}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
        {status.data?.sync.last && (
          <p className="mt-3 text-xs text-slate-500">
            Last sync: {fmtDate((status.data.sync.last as { finished_at?: string }).finished_at)}
          </p>
        )}
        <p className="mt-2 text-xs text-slate-400">Browser-based scraping. Runs on this machine.</p>
      </Card>

      <Card title="Outlook (local app)">
        <QueryState q={status}>
          <div className="flex items-center gap-3">
            <Badge tone={mailCount > 0 ? 'green' : 'gray'}>
              {mailCount > 0 ? 'Active' : 'No data'}
            </Badge>
            <span className="text-sm text-slate-600">{mailCount} email{mailCount !== 1 ? 's' : ''} ingested</span>
          </div>
        </QueryState>
        <p className="mt-3 text-xs text-slate-500">
          Emails are pushed from the Outlook app on this machine via a local script. Sign-in is managed
          in Outlook itself — no action needed here.
        </p>
        <p className="mt-1 text-xs text-slate-400">
          If emails stop appearing, check that Outlook is open and signed in on this computer.
        </p>
      </Card>
    </div>
  )
}
