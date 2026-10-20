import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNotifyError } from '../notify'
import type {
  AuthState, Category, Change, ErrorsData, Eval, HistoryEntry, Item, ItemDetail, Label,
  LLMProviderConfig, Priority, SettingsData, Status, Task, TriageRow,
} from './types'

/** '' in production (same origin as the backend), '/api' in dev (Vite proxy). */
export const API_BASE = import.meta.env.VITE_API_BASE ?? ''

type Params = Record<string, string | number | boolean | null | undefined>

function url(path: string, params?: Params): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  }
  const q = qs.toString()
  return `${API_BASE}${path}${q ? `?${q}` : ''}`
}

export async function api<T>(path: string, init?: RequestInit & { params?: Params }): Promise<T> {
  const res = await fetch(url(path, init?.params), {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json', ...init.headers } : init?.headers,
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = JSON.stringify((await res.json()).detail ?? detail) } catch { /* not JSON */ }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const itemPath = (id: string) => `/items/${id.split('/').map(encodeURIComponent).join('/')}`
export const fileUrl = (id: string) => `${API_BASE}${itemPath(id)}/file`
export const calendarUrl = () => new URL(`${API_BASE}/calendar.ics`, window.location.origin).href

// ── Queries ──────────────────────────────────────────────────────────────────

export const useAuth = () =>
  useQuery({
    queryKey: ['auth'],
    queryFn: () => api<AuthState>('/auth/brightspace'),
    // Poll fast while a login/check/sync is running so the UI follows along.
    refetchInterval: (q) => (q.state.data?.busy ? 2_000 : 15_000),
  })

export const useStatus = () =>
  useQuery({
    queryKey: ['status'],
    queryFn: () => api<Status>('/status'),
    refetchInterval: (q) => (q.state.data?.sync.busy || q.state.data?.analysis.running ? 3_000 : 30_000),
  })

export interface TriageFilters {
  days?: number
  date_from?: string
  date_to?: string
  categories?: Category[]
  priorities?: Priority[]
  kinds?: string[]
  include_ignored?: boolean
  needs_review?: boolean
}

export const useTriage = (f: TriageFilters) => {
  const params: Record<string, string | number | boolean | undefined> = {
    days: f.days,
    date_from: f.date_from,
    date_to: f.date_to,
    categories: f.categories?.length ? f.categories.join(',') : undefined,
    priorities: f.priorities?.length ? f.priorities.join(',') : undefined,
    kinds: f.kinds?.length ? f.kinds.join(',') : undefined,
    include_ignored: f.include_ignored || undefined,
    needs_review: f.needs_review || undefined,
  }
  return useQuery({
    queryKey: ['triage', f],
    queryFn: () => api<TriageRow[]>('/triage', { params }),
  })
}

export const useTasks = (days = 60) =>
  useQuery({ queryKey: ['tasks', days], queryFn: () => api<Task[]>('/tasks', { params: { days } }) })

export const useUpcoming = (days: number, overdueDays = 0) =>
  useQuery({
    queryKey: ['upcoming', days, overdueDays],
    queryFn: () => api<Item[]>('/upcoming', { params: { days, overdue_days: overdueDays } }),
  })

export const useChanges = (since: string) =>
  useQuery({
    queryKey: ['changes', since],
    queryFn: () => api<Change[]>('/changes', { params: { since, limit: 100 } }),
  })

export interface ItemFilters { q?: string; source?: string; kind?: string; course_id?: string; offset?: number }
export const PAGE = 50

export const useItems = (f: ItemFilters) =>
  useQuery({
    queryKey: ['items', f],
    queryFn: () => api<Item[]>('/items', { params: { ...f, limit: PAGE } }),
    placeholderData: (prev) => prev,
  })

export const useCourses = () =>
  useQuery({
    queryKey: ['items', 'courses'],
    queryFn: () => api<Item[]>('/items', { params: { kind: 'course', limit: 1000 } }),
    staleTime: 10 * 60_000,
  })

export const useItem = (id: string | null) =>
  useQuery({ queryKey: ['item', id], queryFn: () => api<ItemDetail>(itemPath(id!)), enabled: !!id })

export const useHistory = (id: string | null) =>
  useQuery({
    queryKey: ['history', id],
    queryFn: () => api<HistoryEntry[]>(`${itemPath(id!)}/history`),
    enabled: !!id,
  })

export const useEval = (cutoff: number) =>
  useQuery({ queryKey: ['eval', cutoff], queryFn: () => api<Eval>('/triage/eval', { params: { cutoff } }) })

export const useLlmStatus = () =>
  useQuery({ queryKey: ['llm'], queryFn: () => api<Record<string, unknown>>('/llm/status'), staleTime: 60_000 })

export const useSettings = () =>
  useQuery({ queryKey: ['settings'], queryFn: () => api<SettingsData>('/settings'), staleTime: 5_000 })

export const useErrors = () =>
  useQuery({ queryKey: ['errors'], queryFn: () => api<ErrorsData>('/errors'), refetchInterval: 10_000 })

// ── Mutations ────────────────────────────────────────────────────────────────

export function useLabel() {
  const qc = useQueryClient()
  const notify = useNotifyError()
  return useMutation({
    mutationFn: (v: { id: string; category: Category | null; priority: Priority | null; note?: string | null }) =>
      post<Label>(`${itemPath(v.id)}/label`, { category: v.category, priority: v.priority, note: v.note ?? null }),
    onSuccess: (label, v) => {
      // Patch cached triage lists in place so the queue doesn't jump around while labelling.
      qc.setQueriesData<TriageRow[]>({ queryKey: ['triage'] }, (rows) =>
        rows?.map((r) => r.id !== v.id ? r : {
          ...r,
          label_category: label.category, label_priority: label.priority, label_note: label.note,
          category: label.category ?? r.triage.category, priority: label.priority ?? r.triage.priority,
          corrected: !!(label.category || label.priority), needs_review: false,
        }))
      qc.invalidateQueries({ queryKey: ['item', v.id] })
      qc.invalidateQueries({ queryKey: ['eval'] })
    },
    onError: (e: Error) => notify(e.message),
  })
}

function useAction<T = unknown, V = void>(fn: (v: V) => Promise<T>, invalidate: string[][]) {
  const qc = useQueryClient()
  const notify = useNotifyError()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => invalidate.forEach((queryKey) => qc.invalidateQueries({ queryKey })),
    onError: (e: Error) => notify(e.message),
  })
}

export const useSync = () => useAction(() => post('/sync/brightspace'), [['auth'], ['status']])
export const useLogin = () => useAction(() => post('/auth/brightspace/login', {}), [['auth'], ['status']])
export const useAuthCheck = () => useAction(() => post<AuthState>('/auth/brightspace/check'), [['auth'], ['status']])
export const useAnalyze = () =>
  useAction((body: { triage: boolean; briefs: boolean; force: boolean }) => post('/analyze', body), [['status']])
export const useSetLLMProvider = () =>
  useAction((v: { task: string } & LLMProviderConfig) => post('/settings/llm', v), [['settings'], ['llm']])
export const useGetLLMModels = () =>
  useMutation({
    mutationFn: (params: { endpoint: string; api_key?: string }) =>
      api<{ models: string[] }>('/settings/llm/models', { params }),
  })
