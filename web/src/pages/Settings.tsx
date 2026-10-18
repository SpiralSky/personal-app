import { useState } from 'react'
import { useGetLLMModels, useSetLLMProvider, useSettings } from '../api/client'
import type { LLMProvider, LLMTask } from '../api/types'
import { Badge, Button, Card, QueryState } from '../components/ui'
import type { Tone } from '../components/format'

const PROVIDERS: readonly LLMProvider[] = ['claude', 'local', 'auto', 'off', 'custom']
const PROVIDER_TONE: Record<string, Tone> = { claude: 'green', local: 'blue', custom: 'violet' }

type ProviderType = 'claude' | 'local' | 'auto' | 'off' | 'custom'

interface ConfigPanelState {
  providerType: ProviderType
  endpoint: string
  model: string
  apiKey: string
  thinking: boolean
  availableModels: string[]
  fetchingModels: boolean
}

function TaskRow({ task, info, fallbackModel }: { task: string; info: LLMTask | null; fallbackModel: string }) {
  const save = useSetLLMProvider()
  const fetchModels = useGetLLMModels()
  const [editing, setEditing] = useState(false)
  const [config, setConfig] = useState<ConfigPanelState>({
    providerType: (info?.provider as ProviderType) ?? 'off',
    endpoint: info?.endpoint || info?.url || 'http://127.0.0.1:8080/v1',
    model: info?.model || fallbackModel || '',
    apiKey: '',
    thinking: info?.thinking ?? false,
    availableModels: [],
    fetchingModels: false,
  })

  const currentProvider = info?.provider ?? 'off'
  const currentModel = info?.model || fallbackModel || '—'
  const currentEndpoint = info?.endpoint || info?.url

  const handleFetchModels = async () => {
    if (!config.endpoint) return
    setConfig(prev => ({ ...prev, fetchingModels: true }))
    try {
      const result = await fetchModels.mutateAsync({
        endpoint: config.endpoint,
        api_key: config.apiKey || undefined
      })
      setConfig(prev => ({ ...prev, availableModels: result.models, fetchingModels: false }))
      if (result.models.length > 0 && !config.model) {
        setConfig(prev => ({ ...prev, model: result.models[0] }))
      }
    } catch (err) {
      setConfig(prev => ({ ...prev, fetchingModels: false, availableModels: [] }))
      console.error('Failed to fetch models:', err)
    }
  }

  const handleSave = () => {
    if (config.providerType === 'custom') {
      save.mutate({
        task,
        custom: {
          endpoint: config.endpoint,
          model: config.model,
          api_key: config.apiKey || undefined,
          thinking: config.thinking,
        },
      })
    } else {
      save.mutate({ task, preset: config.providerType })
    }
    setEditing(false)
  }

  const handleCancel = () => {
    setEditing(false)
    // Reset to current values
    setConfig({
      providerType: (info?.provider as ProviderType) ?? 'off',
      endpoint: info?.endpoint || info?.url || 'http://127.0.0.1:8080/v1',
      model: info?.model || fallbackModel || '',
      apiKey: '',
      thinking: info?.thinking ?? false,
      availableModels: [],
      fetchingModels: false,
    })
  }

  const showThinkingToggle = config.providerType === 'claude' || config.providerType === 'custom'

  return (
    <>
      <tr className="border-t border-slate-100">
        <td className="py-2 pr-3 font-medium align-top">{task}</td>
        <td className="pr-3 align-top">
          <Badge tone={PROVIDER_TONE[currentProvider] ?? 'gray'}>{currentProvider}</Badge>
        </td>
        <td className="pr-3 text-xs text-slate-500 align-top">
          {info?.error ?? currentModel}
          {currentEndpoint && currentProvider === 'custom' && (
            <div className="text-xs text-slate-400 mt-0.5">{currentEndpoint}</div>
          )}
        </td>
        <td className="align-top">
          <Button
            onClick={() => setEditing(!editing)}
          >
            {editing ? 'Cancel' : 'Configure'}
          </Button>
        </td>
      </tr>
      {editing && (
        <tr className="border-t border-slate-50 bg-slate-50">
          <td colSpan={4} className="p-4">
            <div className="space-y-3">
              {/* Provider type selector */}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Provider Type</label>
                <div className="flex gap-2">
                  {PROVIDERS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                        config.providerType === p
                          ? 'bg-blue-600 text-white'
                          : 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                      onClick={() => setConfig(prev => ({ ...prev, providerType: p }))}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              {/* Custom provider fields */}
              {config.providerType === 'custom' && (
                <div className="space-y-3 pl-4 border-l-2 border-blue-200">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Endpoint URL</label>
                    <input
                      type="text"
                      className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                      value={config.endpoint}
                      onChange={(e) => setConfig(prev => ({ ...prev, endpoint: e.target.value }))}
                      placeholder="http://127.0.0.1:8080/v1"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">API Key (optional)</label>
                    <input
                      type="password"
                      className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                      value={config.apiKey}
                      onChange={(e) => setConfig(prev => ({ ...prev, apiKey: e.target.value }))}
                      placeholder="Leave empty if not required"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Model</label>
                    <div className="flex gap-2">
                      {config.availableModels.length > 0 ? (
                        <select
                          className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                          value={config.model}
                          onChange={(e) => setConfig(prev => ({ ...prev, model: e.target.value }))}
                        >
                          {config.availableModels.map((m) => (
                            <option key={m} value={m}>{m}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
                          value={config.model}
                          onChange={(e) => setConfig(prev => ({ ...prev, model: e.target.value }))}
                          placeholder="Enter model name or fetch from endpoint"
                        />
                      )}
                      <Button
                        onClick={handleFetchModels}
                        disabled={!config.endpoint || config.fetchingModels}
                      >
                        {config.fetchingModels ? 'Fetching...' : 'Fetch Models'}
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Thinking toggle */}
              {showThinkingToggle && (
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id={`thinking-${task}`}
                    className="rounded border-slate-300"
                    checked={config.thinking}
                    onChange={(e) => setConfig(prev => ({ ...prev, thinking: e.target.checked }))}
                  />
                  <label htmlFor={`thinking-${task}`} className="text-sm text-slate-700">
                    Enable extended thinking
                  </label>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2 pt-2">
                <Button
                  onClick={handleSave}
                  disabled={save.isPending || (config.providerType === 'custom' && (!config.endpoint || !config.model))}
                >
                  Save
                </Button>
                <Button onClick={handleCancel} variant="ghost">
                  Cancel
                </Button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function Settings() {
  const settings = useSettings()
  const d = settings.data

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="LLM Providers">
        <QueryState q={settings}>
          {d && (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-slate-500">Claude credentials</span>
                <Badge tone={d.llm.claude_credentials ? 'green' : 'red'}>
                  {d.llm.claude_credentials ? 'available' : 'missing'}
                </Badge>
                <span className="text-slate-500">Local URL</span>
                <code className="text-xs">{d.llm.local_url}</code>
              </div>
              <table className="w-full text-sm">
                <tbody>
                  {Object.entries(d.llm.tasks).map(([task, info]) => (
                    <TaskRow
                      key={`${task}-${info?.provider ?? 'off'}-${info?.model ?? ''}`}
                      task={task}
                      info={info}
                      fallbackModel={info?.provider === 'claude' ? d.llm.claude_model : d.llm.local_model}
                    />
                  ))}
                </tbody>
              </table>
            </>
          )}
        </QueryState>
      </Card>

      <Card title="General">
        <QueryState q={settings}>
          {d && (
            <>
              <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
                <dt className="text-slate-500">bs_hosts</dt>
                <dd>{d.config.bs_hosts.join(', ')}</dd>
                <dt className="text-slate-500">sync_interval_min</dt>
                <dd>{d.config.sync_interval_min}</dd>
                <dt className="text-slate-500">browser_channel</dt>
                <dd>{d.config.browser_channel || '(bundled Chromium)'}</dd>
                <dt className="text-slate-500">bs_skip_courses</dt>
                <dd>{d.config.bs_skip_courses || '—'}</dd>
              </dl>
              <p className="mt-3 text-xs text-slate-500">Set via environment variables.</p>
            </>
          )}
        </QueryState>
      </Card>
    </div>
  )
}
