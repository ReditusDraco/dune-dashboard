import { useState, useEffect } from 'react'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const { dispatch } = useApp()

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get('/settings')
      if (res.data.success) {
        setSettings(res.data.data)
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed to load settings', type: 'error' } })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await client.post('/settings', settings)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Settings saved', type: 'success' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed to save', type: 'error' } })
    } finally {
      setSaving(false)
    }
  }

  const handleChange = (key: string, value: string) => {
    setSettings({ ...settings, [key]: value })
  }

  const addKey = () => {
    const key = prompt('Enter new setting key:')
    if (key) {
      setSettings({ ...settings, [key]: '' })
    }
  }

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Settings</h1>

      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={load}
          disabled={loading}
          className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary-dark disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Reload'}
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-success text-white rounded-lg text-sm font-medium hover:bg-success/80 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
        <button
          onClick={addKey}
          className="px-4 py-2 bg-card-bg border border-border text-text-primary rounded-lg text-sm font-medium hover:bg-hover"
        >
          Add Key
        </button>
      </div>

      <div className="bg-card-bg border border-border rounded-lg p-5 space-y-4 max-w-2xl">
        {Object.entries(settings).length === 0 && !loading && (
          <div className="text-text-muted">No settings found.</div>
        )}
        {Object.entries(settings).map(([key, value]) => (
          <div key={key} className="grid grid-cols-[200px_1fr] gap-4 items-center">
            <label className="text-sm text-text-secondary truncate" title={key}>{key}</label>
            <input
              value={value}
              onChange={(e) => handleChange(key, e.target.value)}
              className="bg-card-bg border border-border rounded px-3 py-2 text-sm text-text-primary"
            />
          </div>
        ))}
      </div>
    </div>
  )
}
