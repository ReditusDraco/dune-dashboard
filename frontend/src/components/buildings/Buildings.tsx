import { useState } from 'react'
import useSWR from 'swr'
import { Box, Heading, Input, Flex } from '@chakra-ui/react'
import { FiSearch } from 'react-icons/fi'
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
    <Box>
      <Heading as="h1" fontFamily="Playfair Display, serif" color="primary.DEFAULT" fontSize="2xl" mb={6}>
        Buildings
      </Heading>

      <Box position="relative" maxW="md" mb={6}>
        <Input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search buildings..."
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
          { header: 'Class', accessor: 'class_name' },
          { header: 'Map', accessor: 'map' },
          { header: 'Owner', accessor: 'owner_name' },
          {
            header: 'Power',
            accessor: (row) => (
              <Flex gap={1}>
                {row.is_powered ? <Badge label="Powered" variant="success" /> : <Badge label="Unpowered" variant="default" />}
                {row.power_level != null && <Badge label={`Lv ${row.power_level}`} variant="default" />}
              </Flex>
            ),
          },
          { header: 'Instances', accessor: 'instance_count' },
        ]}
        data={buildingList}
        loading={isLoading}
      />
    </Box>
  )
}
