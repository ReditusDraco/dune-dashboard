import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useSWR from 'swr'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import { useDebounce } from '../../hooks/useDebounce'
import DataTable from '../common/DataTable'
import Badge from '../common/Badge'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

interface Player {
  player_controller_id: number | null
  account_id: number | null
  character_name: string
  account_email: string | null
  funcom_id: string | null
  faction_name: string | null
  map: string | null
  online_status: string
  life_state: string | null
  last_login_time: string | null
}

export default function PlayerExplorer() {
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)
  const navigate = useNavigate()
  const { dispatch } = useApp()

  const { data: players, isLoading } = useSWR(
    debouncedSearch.length >= 2
      ? `/players?q=${encodeURIComponent(debouncedSearch)}&limit=25`
      : null,
    fetcher,
    { refreshInterval: 30000 }
  )

  const handleAction = async (accountId: number, action: string, payload: Record<string, unknown> = {}) => {
    try {
      let res
      if (action === 'cheater') {
        res = await client.post(`/players/${accountId}/cheater`, payload)
      } else if (action === 'tags') {
        res = await client.put(`/players/${accountId}/tags`, payload)
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: `Action "${action}" not yet implemented`, type: 'warning' } })
        return
      }
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Action successful', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Action failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Action failed', type: 'error' } })
    }
  }

  const playerList: Player[] = players?.success ? players.data : []

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Player Explorer</h1>

      <div className="mb-6">
        <div className="relative max-w-md">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, email, or Funcom ID..."
            className="w-full bg-card-bg border border-border rounded-lg px-4 py-2.5 pl-10 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <svg className="absolute left-3 top-3 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0" />
          </svg>
        </div>
      </div>

      <DataTable
        columns={[
          { header: 'Name', accessor: 'character_name' },
          {
            header: 'Status',
            accessor: (row) => (
              <Badge
                label={row.online_status}
                variant={row.online_status === 'Online' ? 'success' : 'default'}
              />
            ),
          },
          { header: 'Funcom ID', accessor: 'funcom_id' },
          { header: 'Faction', accessor: 'faction_name' },
          { header: 'Map', accessor: 'map' },
          {
            header: 'Quick Actions',
            accessor: (row) => (
              <div className="flex gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); handleAction(row.account_id || row.player_controller_id || 0, 'cheater', { cheat_type: 'exploit' }) }}
                  className="text-[10px] text-primary hover:underline"
                >
                  Cheater
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleAction(row.account_id || row.player_controller_id || 0, 'tags', { add: ['reviewed'] }) }}
                  className="text-[10px] text-primary hover:underline"
                >
                  Tag
                </button>
              </div>
            ),
          },
        ]}
        data={playerList}
        onRowClick={(row) => navigate(`/players/${row.account_id || row.player_controller_id || 0}`)}
        loading={isLoading}
      />
    </div>
  )
}
