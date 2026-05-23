import { useState } from 'react'
import useSWR from 'swr'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import DataTable from '../common/DataTable'
import Modal from '../common/Modal'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

interface Guild {
  guild_id: number
  guild_name: string
  guild_description: string | null
  faction_name: string | null
  member_count: number
  online_count: number
}

interface GuildMember {
  player_id: number
  role_id: number
  role_name: string
  player_name: string
  online_status: string
}

export default function GuildManager() {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Guild | null>(null)
  const [detail, setDetail] = useState<any>(null)
  const { dispatch } = useApp()

  const { data: guilds, isLoading } = useSWR(
    search.length >= 2 ? `/guilds?q=${encodeURIComponent(search)}&limit=25` : null,
    fetcher,
    { refreshInterval: 30000 }
  )

  const loadDetail = async (guildId: number) => {
    try {
      const res = await client.get(`/guilds/${guildId}`)
      if (res.data.success) setDetail(res.data.data)
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  const handleDisband = async () => {
    try {
      const res = await client.delete(`/guilds/${selected!.guild_id}`)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Guild disbanded', type: 'success' } })
        setSelected(null)
        setDetail(null)
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  const handleMemberAction = async (action: string, playerId: number, roleId?: number) => {
    try {
      let res
      if (action === 'remove') {
        res = await client.delete(`/guilds/${selected!.guild_id}/members/${playerId}`)
      } else {
        res = await client.put(`/guilds/${selected!.guild_id}/members/${playerId}/role`, { action, role_id: roleId })
      }
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Member updated', type: 'success' } })
        loadDetail(selected!.guild_id)
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  const guildList: Guild[] = guilds?.success ? guilds.data : []

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Guild Manager</h1>

      <div className="mb-6">
        <div className="relative max-w-md">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search guilds..."
            className="w-full bg-card-bg border border-border rounded-lg px-4 py-2.5 pl-10 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <svg className="absolute left-3 top-3 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0" />
          </svg>
        </div>
      </div>

      <DataTable
        columns={[
          { header: 'Name', accessor: 'guild_name' },
          { header: 'Faction', accessor: 'faction_name' },
          { header: 'Members', accessor: 'member_count' },
          { header: 'Online', accessor: 'online_count' },
        ]}
        data={guildList}
        onRowClick={(row) => { setSelected(row); loadDetail(row.guild_id) }}
        loading={isLoading}
      />

      <Modal open={!!selected} title={selected?.guild_name || ''} onClose={() => { setSelected(null); setDetail(null) }} maxWidth="700px">
        {selected && detail && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <InfoRow label="Guild ID" value={selected.guild_id} />
              <InfoRow label="Members" value={selected.member_count} />
              <InfoRow label="Faction" value={selected.faction_name || 'None'} />
              <InfoRow label="Description" value={selected.guild_description || 'None'} />
            </div>

            <div className="border-t border-border pt-4">
              <h4 className="text-text-muted text-xs uppercase tracking-wider mb-3">Members</h4>
              <div className="overflow-x-auto rounded-lg border border-border max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card-bg">
                    <tr className="border-b border-border">
                      <th className="text-left px-3 py-2 text-text-muted text-[11px] uppercase">Name</th>
                      <th className="text-left px-3 py-2 text-text-muted text-[11px] uppercase">Role</th>
                      <th className="text-left px-3 py-2 text-text-muted text-[11px] uppercase">Status</th>
                      <th className="text-left px-3 py-2 text-text-muted text-[11px] uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.members || []).map((m: GuildMember) => (
                      <tr key={m.player_id} className="border-b border-border last:border-0">
                        <td className="px-3 py-2">{m.player_name}</td>
                        <td className="px-3 py-2"><span className="px-2 py-0.5 rounded text-[10px] bg-primary/10 text-primary border border-primary/20">{m.role_name}</span></td>
                        <td className="px-3 py-2 text-xs">{m.online_status}</td>
                        <td className="px-3 py-2 flex gap-1">
                          <button onClick={() => handleMemberAction('promote', m.player_id, 90)} className="text-[10px] text-primary hover:underline">Promote</button>
                          <button onClick={() => handleMemberAction('demote', m.player_id, 50)} className="text-[10px] text-text-muted hover:underline">Demote</button>
                          <button onClick={() => handleMemberAction('remove', m.player_id)} className="text-[10px] text-danger hover:underline">Remove</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex gap-2 pt-4 border-t border-border">
              <button onClick={handleDisband} className="px-3 py-1.5 rounded text-xs font-medium bg-danger/10 border border-danger/30 text-danger hover:bg-danger/20">Disband Guild</button>
            </div>
          </div>
        )}
      </Modal>
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
