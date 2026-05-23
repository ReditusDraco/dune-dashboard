import { useState } from 'react'
import useSWR from 'swr'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

export default function Director() {
  const [tab, setTab] = useState<'battlegroup' | 'config' | 'transfer' | 'fls'>('battlegroup')
  const { dispatch } = useApp()

  const { data: bgData } = useSWR('/director/battlegroup', fetcher, { refreshInterval: 15000 })

  const handlePost = async (endpoint: string, payload: any) => {
    try {
      const res = await client.post(endpoint, payload)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Success', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Director Control</h1>

      <div className="flex gap-1 mb-6 border-b border-border">
        {([
          { key: 'battlegroup', label: 'Battlegroup' },
          { key: 'config', label: 'Config' },
          { key: 'transfer', label: 'Transfer' },
          { key: 'fls', label: 'FLS' },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as any)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'text-primary border-primary'
                : 'text-text-muted border-transparent hover:text-text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'battlegroup' && (
        <div className="bg-card-bg border border-border rounded-lg p-5">
          <h3 className="text-text-muted text-xs uppercase tracking-wider mb-4">Battlegroup State</h3>
          {bgData?.success ? (
            <pre className="text-xs text-text-secondary font-mono bg-code-bg p-4 rounded overflow-auto max-h-[60vh]">
              {JSON.stringify(bgData.data, null, 2)}
            </pre>
          ) : (
            <div className="text-text-muted">Loading battlegroup data...</div>
          )}
        </div>
      )}

      {tab === 'config' && (
        <div className="bg-card-bg border border-border rounded-lg p-5 space-y-4 max-w-xl">
          <h3 className="text-text-muted text-xs uppercase tracking-wider mb-4">Update Config</h3>
          <div>
            <label className="block text-sm text-text-muted mb-2">Map Name</label>
            <input
              id="config-map"
              className="w-full bg-card-bg border border-border rounded-lg px-4 py-2 text-sm"
              placeholder="e.g., HaggaBasin"
            />
          </div>
          <div>
            <label className="block text-sm text-text-muted mb-2">Config JSON</label>
            <textarea
              id="config-json"
              rows={6}
              className="w-full bg-card-bg border border-border rounded-lg px-4 py-3 text-sm font-mono"
              placeholder='{"maxPlayers": 100}'
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => {
                const map = (document.getElementById('config-map') as HTMLInputElement).value
                const json = (document.getElementById('config-json') as HTMLTextAreaElement).value
                handlePost('/director/config', { map, config: JSON.parse(json) })
              }}
              className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium"
            >
              Update Config
            </button>
            <button
              onClick={() => handlePost('/director/config/clear', {})}
              className="px-4 py-2 bg-danger/10 border border-danger/30 text-danger rounded-lg text-sm font-medium"
            >
              Clear Config
            </button>
          </div>
        </div>
      )}

      {tab === 'transfer' && (
        <div className="bg-card-bg border border-border rounded-lg p-5 space-y-4 max-w-xl">
          <h3 className="text-text-muted text-xs uppercase tracking-wider mb-4">Transfer Rules</h3>
          <div className="flex gap-2">
            <button
              onClick={() => handlePost('/director/transfer/clear', {})}
              className="px-4 py-2 bg-danger/10 border border-danger/30 text-danger rounded-lg text-sm font-medium"
            >
              Clear Overrides
            </button>
          </div>
        </div>
      )}

      {tab === 'fls' && (
        <div className="bg-card-bg border border-border rounded-lg p-5 space-y-4 max-w-xl">
          <h3 className="text-text-muted text-xs uppercase tracking-wider mb-4">FLS Settings</h3>
          <div className="flex gap-2">
            <button
              onClick={() => handlePost('/director/fls/clear', {})}
              className="px-4 py-2 bg-danger/10 border border-danger/30 text-danger rounded-lg text-sm font-medium"
            >
              Clear FLS Overrides
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
