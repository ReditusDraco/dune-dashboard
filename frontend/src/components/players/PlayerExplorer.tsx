import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useSWR from 'swr'
import { Box, Heading, Input, Button, HStack } from '@chakra-ui/react'
import { FiSearch } from 'react-icons/fi'
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
    <Box>
      <Heading as="h1" fontFamily="Playfair Display, serif" fontSize="3xl" color="primary.DEFAULT" mb={6}>
        Player Explorer
      </Heading>

      <Box mb={6} maxW="md" position="relative">
        <Box
          position="absolute"
          left={3}
          top="50%"
          transform="translateY(-50%)"
          zIndex={1}
          color="fg.muted"
        >
          <FiSearch size={16} />
        </Box>
        <Input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, email, or Funcom ID..."
          pl={10}
          bg="card.bg"
          borderColor="border"
          borderRadius="lg"
          fontSize="sm"
          _placeholder={{ color: 'fg.muted' }}
        />
      </Box>

      <DataTable
        columns={[
          { header: 'Name', accessor: 'character_name' },
          {
            header: 'Status',
            accessor: (row) => (
                <Badge
                label={(row as any).online_status}
                variant={(row as any).online_status === 'Online' ? 'success' : 'default'}
              />
            ),
          },
          { header: 'Funcom ID', accessor: 'funcom_id' },
          { header: 'Faction', accessor: 'faction_name' },
          { header: 'Map', accessor: 'map' },
          {
            header: 'Quick Actions',
            accessor: (row) => (
              <HStack gap={2}>
                <Button
                  onClick={(e) => { e.stopPropagation(); handleAction((row as any).account_id || (row as any).player_controller_id || 0, 'cheater', { cheat_type: 'exploit' }) }}
                  variant="ghost"
                  size="xs"
                  color="primary.DEFAULT"
                  fontSize="10px"
                  p={0}
                  h="auto"
                  minW="auto"
                  _hover={{ textDecoration: 'underline' }}
                >
                  Cheater
                </Button>
                <Button
                  onClick={(e) => { e.stopPropagation(); handleAction((row as any).account_id || (row as any).player_controller_id || 0, 'tags', { add: ['reviewed'] }) }}
                  variant="ghost"
                  size="xs"
                  color="primary.DEFAULT"
                  fontSize="10px"
                  p={0}
                  h="auto"
                  minW="auto"
                  _hover={{ textDecoration: 'underline' }}
                >
                  Tag
                </Button>
              </HStack>
            ),
          },
        ]}
        data={playerList}
        onRowClick={(row) => navigate(`/players/${row.account_id || row.player_controller_id || 0}`)}
        loading={isLoading}
      />
    </Box>
  )
}
