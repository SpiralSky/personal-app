// Shapes returned by the campus-assistant API (see src/campus_assistant/store.py, analysis/schemas.py).

export const CATEGORIES = [
  'action_required', 'deadline', 'notice', 'opportunity', 'personal', 'system', 'newsletter', 'other',
] as const
export type Category = (typeof CATEGORIES)[number]

export const PRIORITIES = ['urgent', 'soon', 'whenever', 'ignore'] as const
export type Priority = (typeof PRIORITIES)[number]

export interface Item {
  id: string
  source: string
  kind: string
  external_id: string
  title: string
  body: string
  url: string | null
  course_id: string | null
  course_name: string | null
  occurred_at: string | null
  due_at: string | null
  starts_at: string | null
  ends_at: string | null
  data: Record<string, unknown>
  first_seen: string
  deleted_at?: string | null
}

export interface FileInfo {
  path: string
  filename: string
  content_type: string
}

export interface Analysis {
  task: string
  provider: string
  model: string | null
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
}

export interface Label {
  item_id: string
  category: Category | null
  priority: Priority | null
  note: string | null
  created_at: string
}

export interface ItemDetail extends Item {
  file: FileInfo | null
  analyses: Record<string, Analysis>
  label: Label | null
}

export interface HistoryEntry {
  content_hash: string
  snapshot: string
  replaced_at: string
}

export interface Action { what: string; due: string | null }
export interface DatedThing { what: string; when: string; kind: 'deadline' | 'event' | 'other' }
export interface Opportunity {
  kind: string
  title: string
  deadline: string | null
  eligibility: string | null
  cost: string | null
  link: string | null
}
export interface Link { label: string; url: string }

export interface ClassifierDecision { label: string; p: number }

export interface MessageTriage {
  category: Category
  priority: Priority
  summary: string
  actions: Action[]
  dates: DatedThing[]
  opportunity: Opportunity | null
  links: Link[]
  decided_by?: string
  needs_review?: boolean
  classification?: { category?: ClassifierDecision; priority?: ClassifierDecision }
}

export interface TriageRow {
  id: string
  source: string
  kind: string
  title: string
  url: string | null
  course_name: string | null
  occurred_at: string | null
  sender: string | null
  provider: string
  model: string | null
  error: string | null
  label_category: Category | null
  label_priority: Priority | null
  label_note: string | null
  triage: MessageTriage
  category: Category
  priority: Priority
  corrected: boolean
  decided_by: string | null
  needs_review: boolean
}

export interface PlanStep { step: string; target_date: string | null; est_hours: number | null }

export interface TaskBrief {
  summary: string
  deliverables: string[]
  requirements: string[]
  submission: string | null
  weightage: string | null
  relevant_files: string[]
  plan: PlanStep[]
  open_questions: string[]
  confidence: 'high' | 'medium' | 'low'
}

export interface Task extends Item {
  brief: TaskBrief | null
  brief_meta: { provider: string; model: string | null; created_at: string; error: string | null } | null
}

export interface Change {
  id: number
  item_id: string
  at: string
  change: 'created' | 'updated' | 'removed' | 'restored'
  fields: string[]
  source: string
  kind: string
  title: string
  course_name: string | null
  due_at: string | null
}

export type AuthStateName = 'ok' | 'login_required' | 'unknown'

export interface HostAuth {
  state: AuthStateName
  user?: string | null
  checked_at?: string
  since?: string
  detail?: string | null
}

export interface AuthState {
  state: AuthStateName
  hosts: Record<string, HostAuth>
  login_in_progress: boolean
  busy: 'sync' | 'check' | 'login' | null
}

export interface Status {
  stats: { source: string; kind: string; n: number }[]
  auth: { brightspace: AuthState }
  sync: { busy: string | null; last: Record<string, unknown> | null }
  analysis: { auto: boolean; running: boolean; last: Record<string, unknown> | null }
}

export interface EvalBucket { range: string; n: number; correct: number; accuracy: number | null }

export interface EvalPart {
  n: number
  final_accuracy: number | null
  classifier_accuracy: number | null
  classifier_accuracy_above_cutoff: number | null
  classifier_coverage_above_cutoff: number | null
  buckets: EvalBucket[]
}

export interface Eval {
  labelled: number
  cutoff: number
  category?: EvalPart
  priority?: EvalPart
}

export type LLMProvider = 'claude' | 'local' | 'auto' | 'off' | 'custom'

export interface LLMTask {
  provider?: string
  model?: string
  url?: string
  endpoint?: string
  thinking?: boolean
  reachable?: boolean
  error?: string
}

export interface CustomProviderConfig {
  endpoint: string
  model: string
  api_key?: string
  thinking?: boolean
}

export interface LLMProviderConfig {
  preset?: 'claude' | 'local' | 'auto' | 'off'
  custom?: CustomProviderConfig
}

export interface SettingsData {
  llm: {
    tasks: Record<string, LLMTask | null>
    claude_model: string
    local_url: string
    local_model: string
    claude_credentials: boolean
  }
  config: {
    bs_hosts: string[]
    sync_interval_min: number
    browser_channel: string
    bs_skip_courses: string | null
  }
}

export interface ErrorEntry { time: string; level: string; logger: string; message: string }

export interface ErrorsData { errors: ErrorEntry[]; count: number }
