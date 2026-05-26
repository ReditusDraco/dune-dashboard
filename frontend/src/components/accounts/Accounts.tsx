import { useState } from 'react'
import useSWR from 'swr'
import { Box, Heading, Input } from '@chakra-ui/react'
import { FiSearch } from 'react-icons/fi'
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
    <Box>
      <Heading as="h1" fontFamily="Playfair Display, serif" color="primary.DEFAULT" fontSize="2xl" mb={6}>
        Accounts
      </Heading>

      <Box position="relative" maxW="md" mb={6}>
        <Input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search accounts..."
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
          { header: 'Email', accessor: 'email' },
          { header: 'Funcom ID', accessor: 'funcom_id' },
          { header: 'Characters', accessor: 'character_count' },
          { header: 'Last Login', accessor: 'last_login' },
        ]}
        data={accountList}
        loading={isLoading}
      />
    </Box>
  )
}
