import { useState } from 'react'
import useSWR from 'swr'
import { Box, Heading, Input, Button } from '@chakra-ui/react'
import { FiSearch } from 'react-icons/fi'
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
    <Box>
      <Heading as="h1" fontFamily="Playfair Display, serif" color="primary.DEFAULT" fontSize="2xl" mb={6}>
        Vehicles
      </Heading>

      <Box position="relative" maxW="md" mb={6}>
        <Input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search vehicles..."
          bg="card.bg"
          borderColor="border"
          borderRadius="lg"
          px={4}
          py={2.5}
          pl={10}
          fontSize="sm"
          color="fg"
          _placeholder={{ color: 'fg.muted' }}
          _focus={{ borderColor: 'primary.DEFAULT', boxShadow: '0 0 0 1px var(--chakra-colors-primary-DEFAULT)' }}
          _focusVisible={{ outline: 'none' }}
        />
        <Box position="absolute" left={3} top="50%" transform="translateY(-50%)" color="fg.muted">
          <FiSearch size={16} />
        </Box>
      </Box>

      <DataTable
        columns={[
          { header: 'Name', accessor: 'display_name' },
          { header: 'Class', accessor: 'class_name' },
          { header: 'Map', accessor: 'map' },
          { header: 'Owner', accessor: 'owner_name' },
          {
            header: 'Actions',
            accessor: (row) => (
              <Box display="flex" gap={2}>
                <Button
                  variant="ghost"
                  size="xs"
                  color="primary.DEFAULT"
                  _hover={{ textDecoration: 'underline' }}
                  onClick={(e) => { e.stopPropagation(); handleAction((row as any).id, 'repair') }}
                >
                  Repair
                </Button>
                <Button
                  variant="ghost"
                  size="xs"
                  color="danger.DEFAULT"
                  _hover={{ textDecoration: 'underline' }}
                  onClick={(e) => { e.stopPropagation(); handleAction((row as any).id, 'destroy') }}
                >
                  Destroy
                </Button>
              </Box>
            ),
          },
        ]}
        data={vehicleList}
        loading={isLoading}
      />
    </Box>
  )
}
