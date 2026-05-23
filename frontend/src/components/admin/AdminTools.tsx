import { useState } from 'react'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

const SCOPE_OPTIONS = ['all', 'server', 'partition']
const SERVER_OPTIONS = ['na', 'eu', 'sea', 'sa', 'oc']
const PARTITION_OPTIONS = ['parrish', 'sietch', 'bazar']

export default function AdminTools() {
  const [tab, setTab] = useState<'broadcast' | 'economy' | 'world' | 'character' | 'functions' | 'raw' | 'audit'>('broadcast')
  const { dispatch } = useApp()

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Admin Tools</h1>

      <div className="flex gap-1 mb-6 border-b border-border overflow-x-auto no-scrollbar">
        {([
          { key: 'broadcast', label: 'Broadcast' },
          { key: 'economy', label: 'Economy' },
          { key: 'world', label: 'World' },
          { key: 'character', label: 'Character' },
          { key: 'functions', label: 'Functions' },
          { key: 'raw', label: 'Raw Query' },
          { key: 'audit', label: 'Audit Log' },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as any)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              tab === t.key
                ? 'text-primary border-primary'
                : 'text-text-muted border-transparent hover:text-text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'broadcast' && <BroadcastTab dispatch={dispatch} />}
      {tab === 'economy' && <EconomyTab dispatch={dispatch} />}
      {tab === 'world' && <WorldTab dispatch={dispatch} />}
      {tab === 'character' && <CharacterTab dispatch={dispatch} />}
      {tab === 'functions' && <FunctionsTab dispatch={dispatch} />}
      {tab === 'raw' && <RawQueryTab dispatch={dispatch} />}
      {tab === 'audit' && <AuditLogTab dispatch={dispatch} />}
    </div>
  )
}

function BroadcastTab({ dispatch }: { dispatch: any }) {
  const [message, setMessage] = useState('')
  const [scope, setScope] = useState('all')
  const [server, setServer] = useState('na')
  const [partition, setPartition] = useState('parrish')
  const [sending, setSending] = useState(false)

  const handleSend = async () => {
    if (!message.trim()) return
    setSending(true)
    try {
      const payload: any = { message: message.trim() }
      if (scope === 'server') payload.server = server
      if (scope === 'partition') {
        payload.server = server
        payload.partition = partition
      }
      const res = await client.post('/broadcast', payload)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Broadcast sent', type: 'success' } })
        setMessage('')
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="max-w-xl">
      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-4">
        <div>
          <label className="block text-sm text-text-muted mb-2">Scope</label>
          <div className="flex gap-2">
            {SCOPE_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setScope(s)}
                className={`px-3 py-1.5 rounded text-xs font-medium border capitalize ${
                  scope === s
                    ? 'bg-primary/10 border-primary text-primary'
                    : 'bg-card-bg border-border text-text-muted hover:text-text-primary'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {scope !== 'all' && (
          <div>
            <label className="block text-sm text-text-muted mb-2">Server</label>
            <select value={server} onChange={(e) => setServer(e.target.value)} className="bg-card-bg border border-border rounded px-3 py-2 text-sm text-text-primary">
              {SERVER_OPTIONS.map((s) => <option key={s} value={s}>{s.toUpperCase()}</option>)}
            </select>
          </div>
        )}

        {scope === 'partition' && (
          <div>
            <label className="block text-sm text-text-muted mb-2">Partition</label>
            <select value={partition} onChange={(e) => setPartition(e.target.value)} className="bg-card-bg border border-border rounded px-3 py-2 text-sm text-text-primary">
              {PARTITION_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        )}

        <div>
          <label className="block text-sm text-text-muted mb-2">Message</label>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={4} className="w-full bg-card-bg border border-border rounded-lg px-4 py-3 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-y" placeholder="Enter broadcast message..." />
        </div>

        <button onClick={handleSend} disabled={sending || !message.trim()} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark disabled:opacity-50 transition-colors">
          {sending ? 'Sending...' : 'Send Broadcast'}
        </button>
      </div>
    </div>
  )
}

function EconomyTab({ dispatch }: { dispatch: any }) {
  const [playerId, setPlayerId] = useState('')
  const [itemForm, setItemForm] = useState({ template_id: '', stack_size: '1', quality: '0', inventory_id: '' })
  const [editForm, setEditForm] = useState({ item_id: '', field: 'stack_size', value: '' })

  const post = async (endpoint: string, payload: any) => {
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-medium text-text-primary">Add Item</h3>
        <input value={playerId} onChange={(e) => setPlayerId(e.target.value)} placeholder="Player ID" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <input value={itemForm.template_id} onChange={(e) => setItemForm({ ...itemForm, template_id: e.target.value })} placeholder="Template ID" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <input value={itemForm.stack_size} onChange={(e) => setItemForm({ ...itemForm, stack_size: e.target.value })} placeholder="Stack Size" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <input value={itemForm.quality} onChange={(e) => setItemForm({ ...itemForm, quality: e.target.value })} placeholder="Quality" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <input value={itemForm.inventory_id} onChange={(e) => setItemForm({ ...itemForm, inventory_id: e.target.value })} placeholder="Inventory ID" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <button onClick={() => post('/items/add', { player_id: parseInt(playerId), template_id: itemForm.template_id, stack_size: parseInt(itemForm.stack_size), quality_level: parseInt(itemForm.quality), inventory_id: parseInt(itemForm.inventory_id) || undefined })} className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary">Add Item</button>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-medium text-text-primary">Edit Item</h3>
        <input value={editForm.item_id} onChange={(e) => setEditForm({ ...editForm, item_id: e.target.value })} placeholder="Item ID" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <select value={editForm.field} onChange={(e) => setEditForm({ ...editForm, field: e.target.value })} className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm">
          {['stack_size', 'quality_level', 'durability', 'ammo'].map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
        <input value={editForm.value} onChange={(e) => setEditForm({ ...editForm, value: e.target.value })} placeholder="New value" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <div className="flex gap-2">
          <button onClick={() => post(`/items/${editForm.item_id}`, { [editForm.field]: editForm.value })} className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary">Update</button>
          <button onClick={() => post(`/items/${editForm.item_id}`, {})} className="px-3 py-1.5 rounded text-xs bg-danger/10 border border-danger/30 text-danger">Delete</button>
        </div>
      </div>
    </div>
  )
}

function WorldTab({ dispatch }: { dispatch: any }) {
  const [tpForm, setTpForm] = useState({ fls_id: '', partition: '', x: '', y: '', z: '' })

  const post = async (endpoint: string, payload: any) => {
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-medium text-text-primary">Teleport Player</h3>
        <input value={tpForm.fls_id} onChange={(e) => setTpForm({ ...tpForm, fls_id: e.target.value })} placeholder="FLS ID / Account ID" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <input value={tpForm.partition} onChange={(e) => setTpForm({ ...tpForm, partition: e.target.value })} placeholder="Partition ID" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <div className="grid grid-cols-3 gap-2">
          <input type="number" value={tpForm.x} onChange={(e) => setTpForm({ ...tpForm, x: e.target.value })} placeholder="X" className="bg-card-bg border border-border rounded px-3 py-2 text-sm" />
          <input type="number" value={tpForm.y} onChange={(e) => setTpForm({ ...tpForm, y: e.target.value })} placeholder="Y" className="bg-card-bg border border-border rounded px-3 py-2 text-sm" />
          <input type="number" value={tpForm.z} onChange={(e) => setTpForm({ ...tpForm, z: e.target.value })} placeholder="Z" className="bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        </div>
        <button onClick={() => post('/teleport', { fls_id: parseInt(tpForm.fls_id), partition_id: tpForm.partition, x: parseFloat(tpForm.x) || 0, y: parseFloat(tpForm.y) || 0, z: parseFloat(tpForm.z) || 0 })} className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary">Teleport</button>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-medium text-text-primary">Spice Control</h3>
        <div className="flex gap-2">
          <button onClick={() => post('/spice/reset', {})} className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary">Reset Spice Fields</button>
          <button onClick={() => post('/spice/spawn', {})} className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary">Force Spawn</button>
        </div>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-medium text-text-primary">Partitions</h3>
        <button onClick={() => client.get('/partitions').then((r) => dispatch({ type: 'ADD_TOAST', payload: { message: `Partitions loaded`, type: 'info' } }))} className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary">List Partitions</button>
      </div>
    </div>
  )
}

function CharacterTab({ dispatch }: { dispatch: any }) {
  const [charId, setCharId] = useState('')
  const [newName, setNewName] = useState('')
  const [demoState, setDemoState] = useState('true')

  const post = async (endpoint: string, payload: any) => {
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-medium text-text-primary">Rename Character</h3>
        <input value={charId} onChange={(e) => setCharId(e.target.value)} placeholder="Account ID / Character ID" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New Name" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <button onClick={() => post(`/characters/${charId}/name`, { name: newName })} className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary">Rename</button>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-medium text-text-primary">Demo State</h3>
        <input value={charId} onChange={(e) => setCharId(e.target.value)} placeholder="Account ID" className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm" />
        <select value={demoState} onChange={(e) => setDemoState(e.target.value)} className="w-full bg-card-bg border border-border rounded px-3 py-2 text-sm">
          <option value="true">Demo</option>
          <option value="false">Normal</option>
        </select>
        <button onClick={() => post(`/accounts/${charId}/demo`, { demo: demoState === 'true' })} className="px-3 py-1.5 rounded text-xs bg-primary/10 border border-primary/20 text-primary">Set Demo State</button>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-3">
        <h3 className="font-medium text-text-primary">Danger Zone</h3>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => { if (confirm('Delete character?')) post(`/characters/${charId}`, {}) }} className="px-3 py-1.5 rounded text-xs bg-danger/10 border border-danger/30 text-danger">Delete Character</button>
          <button onClick={() => { if (confirm('Delete account?')) post(`/accounts/${charId}`, {}) }} className="px-3 py-1.5 rounded text-xs bg-danger/10 border border-danger/30 text-danger">Delete Account</button>
        </div>
      </div>
    </div>
  )
}

function FunctionsTab({ dispatch }: { dispatch: any }) {
  const [schema, setSchema] = useState('')
  const [funcName, setFuncName] = useState('')
  const [args, setArgs] = useState('{}')
  const [result, setResult] = useState('')
  const [running, setRunning] = useState(false)

  const handleExecute = async () => {
    setRunning(true)
    try {
      const parsedArgs = JSON.parse(args || '{}')
      const res = await client.post('/functions/execute', { schema: schema || undefined, function: funcName, args: parsedArgs })
      if (res.data.success) {
        setResult(JSON.stringify(res.data.data, null, 2))
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Function executed', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.message, type: 'error' } })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-text-muted mb-2">Schema (optional)</label>
            <input value={schema} onChange={(e) => setSchema(e.target.value)} className="w-full bg-card-bg border border-border rounded-lg px-4 py-2 text-sm text-text-primary" placeholder="e.g., public" />
          </div>
          <div>
            <label className="block text-sm text-text-muted mb-2">Function Name</label>
            <input value={funcName} onChange={(e) => setFuncName(e.target.value)} className="w-full bg-card-bg border border-border rounded-lg px-4 py-2 text-sm text-text-primary" placeholder="e.g., get_player_stats" />
          </div>
        </div>
        <div>
          <label className="block text-sm text-text-muted mb-2">Arguments (JSON)</label>
          <textarea value={args} onChange={(e) => setArgs(e.target.value)} rows={4} className="w-full bg-card-bg border border-border rounded-lg px-4 py-3 text-sm font-mono text-text-primary focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-y" />
        </div>
        <button onClick={handleExecute} disabled={running || !funcName} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark disabled:opacity-50 transition-colors">
          {running ? 'Running...' : 'Execute'}
        </button>
        {result && <pre className="mt-4 text-xs font-mono bg-code-bg p-4 rounded overflow-auto text-text-secondary">{result}</pre>}
      </div>
    </div>
  )
}

function RawQueryTab({ dispatch }: { dispatch: any }) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState('')
  const [running, setRunning] = useState(false)

  const handleRun = async () => {
    setRunning(true)
    try {
      const res = await client.post('/query', { query })
      if (res.data.success) {
        setResult(JSON.stringify(res.data.data, null, 2))
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Query executed', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || e.message, type: 'error' } })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="max-w-3xl">
      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <label className="text-sm text-text-muted">SQL Query (Read-Only SELECT)</label>
          <span className="text-[10px] text-text-muted uppercase tracking-wider bg-danger/10 px-2 py-0.5 rounded border border-danger/20">Read Only</span>
        </div>
        <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={6} className="w-full bg-card-bg border border-border rounded-lg px-4 py-3 text-sm font-mono text-text-primary focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-y" placeholder="SELECT * FROM public.characters LIMIT 10;" />
        <button onClick={handleRun} disabled={running || !query.trim()} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark disabled:opacity-50 transition-colors">
          {running ? 'Running...' : 'Run Query'}
        </button>
        {result && <pre className="mt-4 text-xs font-mono bg-code-bg p-4 rounded overflow-auto text-text-secondary">{result}</pre>}
      </div>
    </div>
  )
}

function AuditLogTab({ dispatch }: { dispatch: any }) {
  const [limit, setLimit] = useState(50)
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get(`/audit/logs?limit=${limit}`)
      if (res.data.success) setLogs(res.data.data)
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-4">
        <button onClick={load} disabled={loading} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark disabled:opacity-50 transition-colors">
          {loading ? 'Loading...' : 'Load Logs'}
        </button>
        <select value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="bg-card-bg border border-border rounded px-3 py-2 text-sm text-text-primary">
          {[10, 25, 50, 100, 250].map((n) => <option key={n} value={n}>{n} entries</option>)}
        </select>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Time</th>
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Admin</th>
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Action</th>
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Target</th>
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log, i) => (
              <tr key={i} className="border-b border-border last:border-0 hover:bg-hover/50">
                <td className="px-4 py-3 text-text-muted text-xs">{new Date(log.timestamp).toLocaleString()}</td>
                <td className="px-4 py-3">{log.admin_name}</td>
                <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-primary/10 text-primary border border-primary/20">{log.action}</span></td>
                <td className="px-4 py-3">{log.target_type}: {log.target_id}</td>
                <td className="px-4 py-3 text-xs text-text-muted max-w-md truncate">{JSON.stringify(log.details)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
