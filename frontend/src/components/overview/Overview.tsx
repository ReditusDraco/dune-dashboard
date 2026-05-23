import { useState, useEffect } from 'react'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

interface Metrics {
  total_players: number
  online_players: number
  guild_count: number
  active_guilds: number
  server_count: number
  partition_count: number
  total_worth: number
  total_flavor_text: number
}

export default function Overview() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)
  const { dispatch } = useApp()

  useEffect(() => {
    async function load() {
      try {
        const res = await client.get('/stats')
        if (res.data.success) {
          setMetrics(res.data.data)
        }
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()

    const es = new EventSource('/api/events/stream')
    es.addEventListener('metrics', (e) => {
      try {
        setMetrics(JSON.parse(e.data))
      } catch {}
    })
    return () => es.close()
  }, [])

  const statCards = metrics
    ? [
        { label: 'Total Players', value: metrics.total_players.toLocaleString(), icon: '👥' },
        { label: 'Online Players', value: metrics.online_players.toLocaleString(), icon: '🟢' },
        { label: 'Guilds', value: metrics.guild_count.toLocaleString(), icon: '🛡️' },
        { label: 'Active Guilds', value: metrics.active_guilds.toLocaleString(), icon: '⚔️' },
        { label: 'Servers', value: metrics.server_count.toLocaleString(), icon: '🖥️' },
        { label: 'Partitions', value: metrics.partition_count.toLocaleString(), icon: '🗺️' },
        { label: 'Total Worth', value: '$' + Math.round(metrics.total_worth).toLocaleString(), icon: '💰' },
        { label: 'Flavor Text', value: metrics.total_flavor_text.toLocaleString(), icon: '📝' },
      ]
    : []

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Dashboard Overview</h1>

      {loading ? (
        <div className="text-text-muted">Loading metrics...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((card) => (
            <div
              key={card.label}
              className="bg-card-bg border border-border rounded-lg p-5 shadow-card"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{card.icon}</span>
              </div>
              <div className="text-2xl font-bold text-text-primary mb-1">{card.value}</div>
              <div className="text-sm text-text-muted">{card.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card-bg border border-border rounded-lg p-5 shadow-card">
          <h2 className="font-serif text-xl text-primary mb-4">Quick Actions</h2>
          <div className="grid grid-cols-2 gap-3">
            <QuickAction label="Broadcast Message" onClick={() => {}} />
            <QuickAction label="Player Search" onClick={() => {}} />
            <QuickAction label="Guild Lookup" onClick={() => {}} />
            <QuickAction label="Server Restart" onClick={() => {}} />
          </div>
        </div>

        <div className="bg-card-bg border border-border rounded-lg p-5 shadow-card">
          <h2 className="font-serif text-xl text-primary mb-4">System Health</h2>
          <div className="space-y-3">
            <HealthRow label="Database" status="ok" detail="Connected" />
            <HealthRow label="SSH Tunnel" status="ok" detail="Connected" />
            <HealthRow label="BG Director" status="ok" detail="Connected" />
            <HealthRow label="RMQ Game" status="ok" detail="Connected" />
          </div>
        </div>
      </div>
    </div>
  )
}

function QuickAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="px-4 py-3 bg-primary/10 border border-primary/20 rounded-lg text-primary text-sm font-medium hover:bg-primary/20 transition-colors text-left"
    >
      {label}
    </button>
  )
}

function HealthRow({ label, status, detail }: { label: string; status: 'ok' | 'warn' | 'error'; detail: string }) {
  const dotColor = status === 'ok' ? '#27ae60' : status === 'warn' ? '#f39c12' : '#c0392b'
  return (
    <div className="flex items-center justify-between text-sm">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: dotColor }} />
        <span className="text-text-secondary">{label}</span>
      </div>
      <span className="text-text-muted">{detail}</span>
    </div>
  )
}
