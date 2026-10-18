import { useErrors } from '../api/client'
import { Badge, Button, Card, QueryState } from '../components/ui'
import { fmtDate, relative } from '../components/format'

export default function Errors() {
  const errors = useErrors()

  return (
    <Card
      title="Recent Errors"
      actions={<Button disabled={errors.isFetching} onClick={() => errors.refetch()}>Refresh</Button>}
    >
      <QueryState q={errors}>
        {errors.data?.count === 0 ? (
          <p className="text-sm text-slate-500">No warnings or errors.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="pb-1 pr-3 font-medium">Time</th>
                <th className="pb-1 pr-3 font-medium">Level</th>
                <th className="pb-1 pr-3 font-medium">Logger</th>
                <th className="pb-1 font-medium">Message</th>
              </tr>
            </thead>
            <tbody>
              {errors.data?.errors.map((e, i) => (
                <tr key={`${e.time}-${i}`} className="border-t border-slate-100 align-top">
                  <td className="py-1 pr-3 whitespace-nowrap text-slate-500" title={fmtDate(e.time)}>{relative(e.time)}</td>
                  <td className="pr-3">
                    <Badge tone={e.level === 'WARNING' ? 'amber' : 'red'}>{e.level}</Badge>
                  </td>
                  <td className="pr-3 whitespace-nowrap text-slate-600">{e.logger}</td>
                  <td className="break-words">{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </QueryState>
    </Card>
  )
}
