import { useState } from 'react'
import useSWR from 'swr'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import DataTable from '../common/DataTable'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

interface Account {
  id: number
  email: string
  funcom_id: string
  character_count: number
  is_demo: boolean
  is_cheater: boolean
  last_login: string
}

export default function Accounts() {
  const [search, setSearch] = useState('')
  const { dispatch } = useApp()

  const { data: accountsData, isLoading } = useSWR(
    search.length >= 2 ? `/accounts?q=${encodeURIComponent(search)}&limit=50` : '/accounts?limit=100',
    fetcher,
    { refreshInterval: 30000 }
  )

  const accountList: Account[] = accountsData?.success ? accountsData.data : []

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Accounts</h1>

      <div className="mb-6">
        <div className="relative max-w-md">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search accounts..."
            className="w-full bg-card-bg border border-border rounded-lg px-4 py-2.5 pl-10 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <svg className="absolute left-3 top-3 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0" />
          </svg>
        </div>
      </div>

      <DataTable
        columns={[
          { header: 'Email', accessor: 'email' },
          { header: 'Funcom ID', accessor: 'funcom_id' },
          { header: 'Characters', accessor: 'character_count' },
          { header: 'Last Login', accessor: 'last_login' },
        ]}
        data={accountList}
        loading={isLoading}
      />
    </div>
  )
}
