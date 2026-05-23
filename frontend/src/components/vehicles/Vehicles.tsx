import { useState } from 'react'
import useSWR from 'swr'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import DataTable from '../common/DataTable'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

interface Vehicle {
  id: number
  class_name: string
  display_name: string
  map: string
  owner_name: string
  online_status: string
}

export default function Vehicles() {
  const [search, setSearch] = useState('')
  const { dispatch } = useApp()

  const { data: vehiclesData, isLoading } = useSWR(
    search.length >= 2 ? `/vehicles?q=${encodeURIComponent(search)}&limit=50` : '/vehicles?limit=100',
    fetcher,
    { refreshInterval: 30000 }
  )

  const vehicleList: Vehicle[] = vehiclesData?.success ? vehiclesData.data : []

  const handleAction = async (id: number, action: string) => {
    try {
      const res = await client.post(`/vehicles/${id}/${action}`, {})
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Action successful', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">Vehicles</h1>

      <div className="mb-6">
        <div className="relative max-w-md">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search vehicles..."
            className="w-full bg-card-bg border border-border rounded-lg px-4 py-2.5 pl-10 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
          />
          <svg className="absolute left-3 top-3 w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0" />
          </svg>
        </div>
      </div>

      <DataTable
        columns={[
          { header: 'Name', accessor: 'display_name' },
          { header: 'Class', accessor: 'class_name' },
          { header: 'Map', accessor: 'map' },
          { header: 'Owner', accessor: 'owner_name' },
          {
            header: 'Actions',
            accessor: (row) => (
              <div className="flex gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); handleAction(row.id, 'repair') }}
                  className="text-xs text-primary hover:underline"
                >
                  Repair
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleAction(row.id, 'destroy') }}
                  className="text-xs text-danger hover:underline"
                >
                  Destroy
                </button>
              </div>
            ),
          },
        ]}
        data={vehicleList}
        loading={isLoading}
      />
    </div>
  )
}
