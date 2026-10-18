export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

// ── Formatting ───────────────────────────────────────────────────────────────

const dateFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
const timeFmt = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })

export function fmtDate(iso: string | null | undefined, withTime = true): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  // Date-only values (YYYY-MM-DD) have no meaningful time.
  return withTime && iso.length > 10 ? `${dateFmt.format(d)} ${timeFmt.format(d)}` : dateFmt.format(d)
}

export function relative(iso: string | null | undefined): string {
  if (!iso) return ''
  const ms = new Date(iso).getTime() - Date.now()
  const abs = Math.abs(ms)
  const [n, unit] =
    abs < 3_600_000 ? [Math.round(abs / 60_000), 'min'] :
    abs < 86_400_000 ? [Math.round(abs / 3_600_000), 'h'] :
    [Math.round(abs / 86_400_000), 'd']
  return ms >= 0 ? `in ${n}${unit}` : `${n}${unit} ago`
}

export const isPast = (iso: string | null | undefined) => !!iso && new Date(iso).getTime() < Date.now()
export const humanize = (s: string) => s.replace(/_/g, ' ')

export const TONES = {
  gray: 'bg-slate-100 text-slate-700',
  red: 'bg-red-100 text-red-800',
  amber: 'bg-amber-100 text-amber-800',
  green: 'bg-emerald-100 text-emerald-800',
  blue: 'bg-sky-100 text-sky-800',
  violet: 'bg-violet-100 text-violet-800',
} as const
export type Tone = keyof typeof TONES

export const PRIORITY_TONE: Record<string, Tone> = { urgent: 'red', soon: 'amber', whenever: 'gray', ignore: 'gray' }
export const CATEGORY_TONE: Record<string, Tone> = {
  action_required: 'red', deadline: 'amber', opportunity: 'green', personal: 'violet',
  notice: 'blue', system: 'gray', newsletter: 'gray', other: 'gray',
}
