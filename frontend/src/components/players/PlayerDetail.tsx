import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useSWR from 'swr'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import Badge from '../common/Badge'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

export default function PlayerDetail() {
  const { accountId } = useParams<{ accountId: string }>()
  const navigate = useNavigate()
  const { dispatch } = useApp()
  const [activeTab, setActiveTab] = useState('overview')

  const { data: detail } = useSWR(
    accountId ? `/players/${accountId}` : null,
    fetcher,
    { refreshInterval: 30000 }
  )

  const player = detail?.success ? detail.data : null

  const handleAction = async (endpoint: string, payload: any = {}) => {
    try {
      const res = await client.post(endpoint, payload)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Action successful', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Action failed', type: 'error' } })
    }
  }

  if (!player) {
    return <div className="text-text-muted">Loading player details...</div>
  }

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'inventory', label: 'Inventory' },
    { key: 'vehicles', label: 'Vehicles' },
    { key: 'buildings', label: 'Buildings' },
    { key: 'progression', label: 'Progression' },
    { key: 'actions', label: 'Actions' },
  ]

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => navigate('/players')}
          className="text-text-muted hover:text-text-primary text-sm"
        >
          &larr; Back to Players
        </button>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-serif text-3xl text-primary">{player.character_name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge
              label={player.online_status}
              variant={player.is_online ? 'success' : 'default'}
            />
            {player.faction_name && (
              <span className="text-sm text-text-secondary">{player.faction_name}</span>
            )}
            {player.tags?.map((tag: string) => (
              <Badge key={tag} label={tag} variant="warning" />
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-1 mb-6 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === t.key
                ? 'text-primary border-primary'
                : 'text-text-muted border-transparent hover:text-text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewTab player={player} />}
      {activeTab === 'inventory' && <InventoryTab player={player} />}
      {activeTab === 'vehicles' && <VehiclesTab player={player} />}
      {activeTab === 'buildings' && <BuildingsTab player={player} />}
      {activeTab === 'progression' && <ProgressionTab player={player} />}
      {activeTab === 'actions' && <ActionsTab player={player} onAction={handleAction} />}
    </div>
  )
}

function OverviewTab({ player }: { player: any }) {
  const vitals = player.vitals || {}
  const currency = player.currency || []

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-card-bg border border-border rounded-lg p-5">
        <h3 className="font-serif text-lg text-primary mb-4">Character Info</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <InfoRow label="Account ID" value={player.account_id} />
          <InfoRow label="Controller ID" value={player.player_controller_id} />
          <InfoRow label="Pawn ID" value={player.player_pawn_id} />
          <InfoRow label="Email" value={player.account_email} />
          <InfoRow label="Funcom ID" value={player.funcom_id} />
          <InfoRow label="Map" value={player.map} />
          <InfoRow label="Life State" value={player.life_state} />
          <InfoRow label="Last Login" value={player.last_login_time} />
        </div>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5">
        <h3 className="font-serif text-lg text-primary mb-4">Vitals</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <InfoRow label="Health" value={`${vitals.current_health ?? '?'}/${vitals.max_health ?? '?'}`} />
          <InfoRow label="Hydration" value={vitals.current_hydration ?? '?'} />
          <InfoRow label="Dehydration" value={vitals.dehydration_penalty ?? '?'} />
          <InfoRow label="Spice" value={vitals.current_spice ?? '?'} />
          <InfoRow label="Addiction" value={vitals.spice_addiction_level ?? '?'} />
          <InfoRow label="Tolerance" value={vitals.spice_tolerance ?? '?'} />
        </div>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5">
        <h3 className="font-serif text-lg text-primary mb-4">Currency</h3>
        <div className="space-y-2">
          {currency.length === 0 && <span className="text-text-muted text-sm">No currency data</span>}
          {currency.map((c: any) => (
            <div key={c.currency_id} className="flex justify-between text-sm">
              <span className="text-text-secondary">{c.currency_label}</span>
              <span className="text-text-primary font-mono">{c.balance}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5">
        <h3 className="font-serif text-lg text-primary mb-4">Landsraad</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          {player.landsraad ? (
            <>
              <InfoRow label="Daily Charges" value={player.landsraad.daily_reward_charges} />
              <InfoRow label="Last Term" value={player.landsraad.last_viewed_term_id} />
            </>
          ) : (
            <span className="text-text-muted">No landsraad data</span>
          )}
        </div>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5">
        <h3 className="font-serif text-lg text-primary mb-4">Faction Reputation</h3>
        <div className="space-y-2">
          {(player.faction_reputation || []).length === 0 && <span className="text-text-muted text-sm">No reputation data</span>}
          {(player.faction_reputation || []).map((r: any) => (
            <div key={r.faction_id} className="flex justify-between text-sm">
              <span className="text-text-secondary">{r.faction_name || `Faction ${r.faction_id}`}</span>
              <span className="text-text-primary font-mono">{r.reputation_amount}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <div className="text-text-muted text-xs uppercase tracking-wider">{label}</div>
      <div className="text-text-primary font-mono">{value ?? 'N/A'}</div>
    </div>
  )
}

function InventoryTab({ player }: { player: any }) {
  const inventories = player.inventories || []
  const [selectedInv, setSelectedInv] = useState<any>(null)

  return (
    <div>
      <h3 className="font-serif text-xl text-primary mb-4">Inventories</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {inventories.map((inv: any) => (
          <button
            key={inv.inventory_id}
            onClick={() => setSelectedInv(inv)}
            className={`text-left p-4 rounded-lg border transition-colors ${
              selectedInv?.inventory_id === inv.inventory_id
                ? 'bg-primary/10 border-primary'
                : 'bg-card-bg border-border hover:bg-hover'
            }`}
          >
            <div className="text-sm font-medium text-text-primary">{inv.inventory_type_label}</div>
            <div className="text-xs text-text-muted mt-1">ID: {inv.inventory_id}</div>
            <div className="text-xs text-text-muted">Items: {inv.items?.length || 0}</div>
          </button>
        ))}
      </div>

      {selectedInv && (
        <div className="bg-card-bg border border-border rounded-lg p-5">
          <h4 className="text-text-primary font-medium mb-3">
            {selectedInv.inventory_type_label} Items
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-3 py-2 text-text-muted text-[11px] uppercase">Item</th>
                  <th className="text-left px-3 py-2 text-text-muted text-[11px] uppercase">Stack</th>
                  <th className="text-left px-3 py-2 text-text-muted text-[11px] uppercase">Quality</th>
                  <th className="text-left px-3 py-2 text-text-muted text-[11px] uppercase">Durability</th>
                </tr>
              </thead>
              <tbody>
                {(selectedInv.items || []).map((item: any, i: number) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="px-3 py-2">{item.template_id}</td>
                    <td className="px-3 py-2 font-mono">{item.stack_size}</td>
                    <td className="px-3 py-2 font-mono">{item.quality_level}</td>
                    <td className="px-3 py-2 font-mono">
                      {item.durability != null ? `${Math.round(item.durability)}/${Math.round(item.max_durability)}` : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function VehiclesTab({ player }: { player: any }) {
  const vehicles = player.vehicles || []

  return (
    <div>
      <h3 className="font-serif text-xl text-primary mb-4">Vehicles</h3>
      {vehicles.length === 0 ? (
        <div className="text-text-muted">No vehicles found.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {vehicles.map((v: any) => (
            <div key={v.id} className="bg-card-bg border border-border rounded-lg p-4">
              <div className="text-text-primary font-medium">{v.display_name || v.class_name}</div>
              <div className="text-xs text-text-muted mt-1">Map: {v.map || 'Unknown'}</div>
              <div className="text-xs text-text-muted font-mono">ID: {v.id}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function BuildingsTab({ player }: { player: any }) {
  const buildings = player.buildings || []
  const landclaims = player.landclaims || []

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-serif text-xl text-primary mb-4">Buildings</h3>
        {buildings.length === 0 ? (
          <div className="text-text-muted">No buildings found.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {buildings.map((b: any) => (
              <div key={b.id} className="bg-card-bg border border-border rounded-lg p-4">
                <div className="text-text-primary font-medium">{b.class_name}</div>
                <div className="text-xs text-text-muted mt-1">Map: {b.map || 'Unknown'}</div>
                <div className="flex gap-2 mt-2">
                  {b.is_powered && <Badge label="Powered" variant="success" />}
                  {b.power_level != null && <Badge label={`Power ${b.power_level}`} variant="default" />}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h3 className="font-serif text-xl text-primary mb-4">Landclaims</h3>
        {landclaims.length === 0 ? (
          <div className="text-text-muted">No landclaims found.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {landclaims.map((l: any) => (
              <div key={l.id} className="bg-card-bg border border-border rounded-lg p-4">
                <div className="text-text-primary font-medium">{l.class_name}</div>
                <div className="text-xs text-text-muted mt-1">Map: {l.map || 'Unknown'}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ProgressionTab({ player }: { player: any }) {
  const specs = player.specialization || []
  const keystones = player.keystones || []

  return (
    <div className="space-y-6">
      <div className="bg-card-bg border border-border rounded-lg p-5">
        <h3 className="font-serif text-lg text-primary mb-4">Specialization Tracks</h3>
        {specs.length === 0 ? (
          <div className="text-text-muted">No specialization data.</div>
        ) : (
          <div className="space-y-3">
            {specs.map((s: any, i: number) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-text-secondary text-sm">{s.track_type}</span>
                <div className="flex items-center gap-4">
                  <span className="text-text-muted text-xs">XP: {s.xp_amount}</span>
                  <Badge label={`Lv ${s.level}`} variant="default" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5">
        <h3 className="font-serif text-lg text-primary mb-4">Keystones</h3>
        {keystones.length === 0 ? (
          <div className="text-text-muted">No keystones.</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {keystones.map((k: any) => (
              <Badge key={k.id} label={k.name} variant="default" />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ActionsTab({ player, onAction }: { player: any; onAction: (endpoint: string, payload?: any) => Promise<void> }) {
  const accountId = player.account_id
  const [newName, setNewName] = useState('')
  const [currencyForm, setCurrencyForm] = useState({ currency_id: '0', amount: '' })
  const [vitalsForm, setVitalsForm] = useState({ health: '', hydration: '', spice: '' })
  const [teleportForm, setTeleportForm] = useState({ partition: '', x: '', y: '', z: '' })
  const [banReason, setBanReason] = useState('')
  const [banDuration, setBanDuration] = useState('0')

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <ActionCard title="Currency">
        <div className="space-y-2">
          <select
            value={currencyForm.currency_id}
            onChange={(e) => setCurrencyForm({ ...currencyForm, currency_id: e.target.value })}
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          >
            <option value="0">Solari Credits</option>
            <option value="1">House Script</option>
            <option value="2">Spice</option>
          </select>
          <input
            type="number"
            value={currencyForm.amount}
            onChange={(e) => setCurrencyForm({ ...currencyForm, amount: e.target.value })}
            placeholder="Amount"
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          />
          <div className="flex gap-2">
            <button
              onClick={() => onAction(`/currency/adjust`, { player_id: accountId, currency_id: parseInt(currencyForm.currency_id), amount: parseFloat(currencyForm.amount) })}
              className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary"
            >
              Adjust
            </button>
            <button
              onClick={() => onAction(`/currency/set`, { player_id: accountId, currency_id: parseInt(currencyForm.currency_id), amount: parseFloat(currencyForm.amount) })}
              className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary"
            >
              Set Exact
            </button>
          </div>
        </div>
      </ActionCard>

      <ActionCard title="Vitals">
        <div className="space-y-2">
          <input
            type="number"
            value={vitalsForm.health}
            onChange={(e) => setVitalsForm({ ...vitalsForm, health: e.target.value })}
            placeholder="Health"
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          />
          <input
            type="number"
            value={vitalsForm.hydration}
            onChange={(e) => setVitalsForm({ ...vitalsForm, hydration: e.target.value })}
            placeholder="Hydration"
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          />
          <input
            type="number"
            value={vitalsForm.spice}
            onChange={(e) => setVitalsForm({ ...vitalsForm, spice: e.target.value })}
            placeholder="Spice"
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          />
          <button
            onClick={() => onAction(`/vitals/set`, { player_id: accountId, health: parseFloat(vitalsForm.health) || undefined, hydration: parseFloat(vitalsForm.hydration) || undefined, spice: parseFloat(vitalsForm.spice) || undefined })}
            className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary"
          >
            Set Vitals
          </button>
        </div>
      </ActionCard>

      <ActionCard title="Teleport">
        <div className="space-y-2">
          <input
            value={teleportForm.partition}
            onChange={(e) => setTeleportForm({ ...teleportForm, partition: e.target.value })}
            placeholder="Partition ID"
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          />
          <div className="grid grid-cols-3 gap-2">
            <input
              type="number"
              value={teleportForm.x}
              onChange={(e) => setTeleportForm({ ...teleportForm, x: e.target.value })}
              placeholder="X"
              className="bg-card-bg border border-border rounded px-3 py-2 text-sm"
            />
            <input
              type="number"
              value={teleportForm.y}
              onChange={(e) => setTeleportForm({ ...teleportForm, y: e.target.value })}
              placeholder="Y"
              className="bg-card-bg border border-border rounded px-3 py-2 text-sm"
            />
            <input
              type="number"
              value={teleportForm.z}
              onChange={(e) => setTeleportForm({ ...teleportForm, z: e.target.value })}
              placeholder="Z"
              className="bg-card-bg border border-border rounded px-3 py-2 text-sm"
            />
          </div>
          <button
            onClick={() => onAction(`/teleport`, { fls_id: accountId, partition_id: teleportForm.partition, x: parseFloat(teleportForm.x) || 0, y: parseFloat(teleportForm.y) || 0, z: parseFloat(teleportForm.z) || 0 })}
            className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary"
          >
            Teleport
          </button>
        </div>
      </ActionCard>

      <ActionCard title="Character">
        <div className="space-y-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New character name"
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onAction(`/characters/${accountId}/name`, { name: newName })}
              className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary"
            >
              Rename
            </button>
            <button
              onClick={() => onAction(`/accounts/${accountId}/demo`, { demo: true })}
              className="px-3 py-1.5 rounded text-xs bg-warning/10 border border-warning/20 text-warning"
            >
              Set Demo
            </button>
            <button
              onClick={() => onAction(`/accounts/${accountId}/demo`, { demo: false })}
              className="px-3 py-1.5 rounded text-xs bg-warning/10 border border-warning/20 text-warning"
            >
              Clear Demo
            </button>
            <button
              onClick={() => {
                if (confirm('Delete this character? This cannot be undone.')) {
                  onAction(`/characters/${accountId}`, {})
                }
              }}
              className="px-3 py-1.5 rounded text-xs bg-danger/10 border border-danger/30 text-danger"
            >
              Delete Character
            </button>
            <button
              onClick={() => {
                if (confirm('Delete this entire account? This cannot be undone.')) {
                  onAction(`/accounts/${accountId}`, {})
                }
              }}
              className="px-3 py-1.5 rounded text-xs bg-danger/10 border border-danger/30 text-danger"
            >
              Delete Account
            </button>
          </div>
        </div>
      </ActionCard>

      <ActionCard title="Moderation">
        <div className="space-y-2">
          <input
            value={banReason}
            onChange={(e) => setBanReason(e.target.value)}
            placeholder="Ban reason"
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          />
          <input
            type="number"
            value={banDuration}
            onChange={(e) => setBanDuration(e.target.value)}
            placeholder="Duration (hours, 0 = permanent)"
            className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm"
          />
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onAction(`/players/${accountId}/ban`, { reason: banReason, duration_hours: parseInt(banDuration) || 0 })}
              className="px-3 py-1.5 rounded text-xs bg-danger/10 border border-danger/30 text-danger"
            >
              Ban Player
            </button>
            <button
              onClick={() => onAction(`/players/${accountId}/unban`, {})}
              className="px-3 py-1.5 rounded text-xs bg-success/10 border border-success/30 text-success"
            >
              Unban Player
            </button>
            <button
              onClick={() => onAction(`/players/${accountId}/kick`, { reason: banReason })}
              className="px-3 py-1.5 rounded text-xs bg-warning/10 border border-warning/20 text-warning"
            >
              Kick Player
            </button>
          </div>
        </div>
      </ActionCard>
    </div>
  )
}

function ActionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-card-bg border border-border rounded-lg p-5">
      <h4 className="text-text-primary font-medium mb-3">{title}</h4>
      {children}
    </div>
  )
}
