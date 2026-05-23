import { useState, useEffect } from 'react'
import useSWR from 'swr'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import Badge from '../common/Badge'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

interface Pod {
  name: string
  namespace: string
  status: string
  restarts: number
  age: string
}

interface Deployment {
  name: string
  namespace: string
  replicas: number
  available: number
}

interface MetricPoint {
  timestamp: string
  cpu_percent: number
  memory_percent: number
}

export default function ServerControl() {
  const [tab, setTab] = useState<'pods' | 'deployments' | 'metrics' | 'firewall' | 'rmq'>('pods')
  const { dispatch } = useApp()

  const { data: pods, mutate: mutatePods } = useSWR('/server/pods', fetcher, { refreshInterval: 15000 })
  const { data: deployments } = useSWR('/server/deployments', fetcher, { refreshInterval: 30000 })
  const { data: metrics } = useSWR('/server/metrics?hours=24', fetcher, { refreshInterval: 60000 })
  const { data: firewall } = useSWR('/server/firewall/status', fetcher, { refreshInterval: 30000 })
  const { data: rmq } = useSWR('/server/rmq/overview', fetcher, { refreshInterval: 30000 })

  const podList: Pod[] = pods?.success ? pods.data : []
  const deploymentList: Deployment[] = deployments?.success ? deployments.data : []
  const metricList: MetricPoint[] = metrics?.success ? metrics.data : []

  const handleRestart = async (deployment: string) => {
    try {
      const res = await client.post(`/server/deployments/${deployment}/restart`)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Restart initiated', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  const handleScale = async (deployment: string, replicas: number) => {
    try {
      const res = await client.post(`/server/deployments/${deployment}/scale`, { replicas })
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Scaled successfully', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Server Control</h1>

      <div className="flex gap-1 mb-6 border-b border-border">
        {(['pods', 'deployments', 'metrics', 'firewall', 'rmq'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors capitalize ${
              tab === t
                ? 'text-primary border-primary'
                : 'text-text-muted border-transparent hover:text-text-primary'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'pods' && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Name</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Namespace</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Status</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Restarts</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Age</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {podList.map((pod) => (
                <tr key={pod.name} className="border-b border-border last:border-0 hover:bg-hover/50">
                  <td className="px-4 py-3 font-mono text-xs">{pod.name}</td>
                  <td className="px-4 py-3">{pod.namespace}</td>
                  <td className="px-4 py-3">
                    <Badge
                      label={pod.status}
                      variant={pod.status === 'Running' ? 'success' : pod.status === 'Pending' ? 'warning' : 'danger'}
                    />
                  </td>
                  <td className="px-4 py-3">{pod.restarts}</td>
                  <td className="px-4 py-3">{pod.age}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleRestart(pod.name)}
                      className="text-xs text-primary hover:underline"
                    >
                      Restart
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'deployments' && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Name</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Namespace</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Replicas</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Available</th>
                <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Actions</th>
              </tr>
            </thead>
            <tbody>
              {deploymentList.map((dep) => (
                <tr key={dep.name} className="border-b border-border last:border-0 hover:bg-hover/50">
                  <td className="px-4 py-3 font-mono text-xs">{dep.name}</td>
                  <td className="px-4 py-3">{dep.namespace}</td>
                  <td className="px-4 py-3">{dep.replicas}</td>
                  <td className="px-4 py-3">{dep.available}</td>
                  <td className="px-4 py-3 flex gap-2">
                    <button
                      onClick={() => handleScale(dep.name, dep.replicas + 1)}
                      className="text-xs px-2 py-1 bg-primary/10 border border-primary/20 rounded text-primary"
                    >
                      +1
                    </button>
                    <button
                      onClick={() => handleScale(dep.name, Math.max(0, dep.replicas - 1))}
                      className="text-xs px-2 py-1 bg-primary/10 border border-primary/20 rounded text-primary"
                    >
                      -1
                    </button>
                    <button
                      onClick={() => handleRestart(dep.name)}
                      className="text-xs px-2 py-1 bg-danger/10 border border-danger/20 rounded text-danger"
                    >
                      Restart
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'metrics' && (
        <div className="bg-card-bg border border-border rounded-lg p-5">
          <h3 className="text-text-muted text-xs uppercase tracking-wider mb-4">Server Metrics (24h)</h3>
          {metricList.length === 0 ? (
            <div className="text-text-muted text-sm">No metrics available</div>
          ) : (
            <div className="space-y-2">
              {metricList.slice(-20).map((m, i) => (
                <div key={i} className="flex items-center gap-4 text-sm">
                  <span className="text-text-muted w-32">{new Date(m.timestamp).toLocaleTimeString()}</span>
                  <div className="flex-1 flex items-center gap-2">
                    <span className="text-text-muted w-8">CPU</span>
                    <div className="flex-1 h-2 bg-border rounded overflow-hidden">
                      <div
                        className="h-full bg-primary"
                        style={{ width: `${Math.min(100, m.cpu_percent)}%` }}
                      />
                    </div>
                    <span className="text-text-secondary w-10 text-right">{m.cpu_percent}%</span>
                  </div>
                  <div className="flex-1 flex items-center gap-2">
                    <span className="text-text-muted w-12">Mem</span>
                    <div className="flex-1 h-2 bg-border rounded overflow-hidden">
                      <div
                        className="h-full bg-success"
                        style={{ width: `${Math.min(100, m.memory_percent)}%` }}
                      />
                    </div>
                    <span className="text-text-secondary w-10 text-right">{m.memory_percent}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'firewall' && (
        <div className="bg-card-bg border border-border rounded-lg p-5">
          <h3 className="text-text-muted text-xs uppercase tracking-wider mb-4">Firewall Status</h3>
          {firewall?.success ? (
            <pre className="text-xs text-text-secondary font-mono bg-code-bg p-4 rounded overflow-auto">
              {JSON.stringify(firewall.data, null, 2)}
            </pre>
          ) : (
            <div className="text-text-muted text-sm">No firewall data available</div>
          )}
        </div>
      )}

      {tab === 'rmq' && (
        <div className="bg-card-bg border border-border rounded-lg p-5">
          <h3 className="text-text-muted text-xs uppercase tracking-wider mb-4">RMQ Overview</h3>
          {rmq?.success ? (
            <pre className="text-xs text-text-secondary font-mono bg-code-bg p-4 rounded overflow-auto">
              {JSON.stringify(rmq.data, null, 2)}
            </pre>
          ) : (
            <div className="text-text-muted text-sm">No RMQ data available</div>
          )}
        </div>
      )}
    </div>
  )
}
