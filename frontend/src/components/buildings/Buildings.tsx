import { useState } from 'react'
import useSWR from 'swr'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import DataTable from '../common/DataTable'
import Badge from '../common/Badge'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

interface Building {
  id: number
  class_name: string
  map: string
  owner_name: string
  is_powered: boolean
  power_level: number | null
  instance_count: number
}

export default function Buildings() {
  const [search, setSearch] = useState('')
  const { dispatch } = useApp()

  const { data: buildingsData, isLoading } = useSWR(
    search.length >= 2 ? `/buildings?q=${encodeURIComponent(search)}&limit=50` : '/buildings?limit=100',
    fetcher,
    { refreshInterval: 30000 }
  )

  const buildingList: Building[] = buildingsData?.success ? buildingsData.data : []

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Buildings</h1>

      <div className="mb-6">
        <div className="relative max-w-md">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search buildings..."
            className="w-full bg-card-bg border border-border rounded-lg px-4 py-2.5 pl-10 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <svg className="absolute left-3 top-3 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0" />
          </svg>
        </div>
      </div>

      <DataTable
        columns={[
          { header: 'Class', accessor: 'class_name' },
          { header: 'Map', accessor: 'map' },
          { header: 'Owner', accessor: 'owner_name' },
          {
            header: 'Power',
            accessor: (row) => (
              <div className="flex gap-1">
                {row.is_powered ? <Badge label="Powered" variant="success" /> : <Badge label="Unpowered" variant="default" />}
                {row.power_level != null && <Badge label={`Lv ${row.power_level}`} variant="default" />}
              </div>
            ),
          },
          { header: 'Instances', accessor: 'instance_count' },
        ]}
        data={buildingList}
        loading={isLoading}
      />
    </div>
  )
}
