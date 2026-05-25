import { useState } from 'react'
import useSWR from 'swr'
import {
  Box,
  Heading,
  Input,
  HStack,
  VStack,
  SimpleGrid,
  Button,
  Table,
  Text,
} from '@chakra-ui/react'
import { FiSearch, FiTrash2, FiAlertTriangle } from 'react-icons/fi'
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

function InfoRow({ label, value }: { label: string; value: any }) {
  return (
    <Box>
      <Text fontSize="xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">
        {label}
      </Text>
      <Text fontFamily="Roboto Mono, monospace" color="fg">
        {value ?? 'N/A'}
      </Text>
    </Box>
  )
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
    <Box>
      <Heading as="h1" fontSize="3xl" fontFamily="Playfair Display, serif" color="primary.DEFAULT" mb={6}>
        Guild Manager
      </Heading>

      <Box position="relative" maxW="md" mb={6}>
        <Box
          position="absolute"
          left={3}
          top="50%"
          transform="translateY(-50%)"
          color="fg.muted"
          zIndex={1}
          pointerEvents="none"
        >
          <FiSearch size={16} />
        </Box>
        <Input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search guilds..."
          pl={10}
          bg="card.bg"
          borderColor="border"
          borderRadius="lg"
          fontSize="sm"
          color="fg"
          _placeholder={{ color: 'fg.muted' }}
          _focus={{ borderColor: 'primary.DEFAULT' }}
        />
      </Box>

      <DataTable
        columns={[
          { header: 'Name', accessor: 'guild_name' },
          { header: 'Faction', accessor: 'faction_name' },
          { header: 'Members', accessor: 'member_count' },
          { header: 'Online', accessor: 'online_count' },
        ]}
        data={guildList}
        onRowClick={(row) => {
          setSelected(row as any)
          loadDetail((row as any).guild_id)
        }}
        loading={isLoading}
      />

      <Modal
        open={!!selected}
        title={selected?.guild_name || ''}
        onClose={() => {
          setSelected(null)
          setDetail(null)
        }}
      >
        {selected && detail && (
          <VStack gap={4} align="stretch">
            <SimpleGrid columns={2} gap={4}>
              <InfoRow label="Guild ID" value={selected.guild_id} />
              <InfoRow label="Members" value={selected.member_count} />
              <InfoRow label="Faction" value={selected.faction_name || 'None'} />
              <InfoRow label="Description" value={selected.guild_description || 'None'} />
            </SimpleGrid>

            <Box borderTopWidth="1px" borderColor="border" pt={4}>
              <Text fontSize="xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted" mb={3}>
                Members
              </Text>
              <Table.ScrollArea borderWidth="1px" borderColor="border" borderRadius="lg" maxH="64">
                <Table.Root size="sm" variant="line" stickyHeader>
                  <Table.Header>
                    <Table.Row bg="bg.subtle">
                      <Table.ColumnHeader
                        fontSize="2xs"
                        textTransform="uppercase"
                        letterSpacing="wider"
                        color="fg.muted"
                      >
                        Name
                      </Table.ColumnHeader>
                      <Table.ColumnHeader
                        fontSize="2xs"
                        textTransform="uppercase"
                        letterSpacing="wider"
                        color="fg.muted"
                      >
                        Role
                      </Table.ColumnHeader>
                      <Table.ColumnHeader
                        fontSize="2xs"
                        textTransform="uppercase"
                        letterSpacing="wider"
                        color="fg.muted"
                      >
                        Status
                      </Table.ColumnHeader>
                      <Table.ColumnHeader
                        fontSize="2xs"
                        textTransform="uppercase"
                        letterSpacing="wider"
                        color="fg.muted"
                      >
                        Actions
                      </Table.ColumnHeader>
                    </Table.Row>
                  </Table.Header>
                  <Table.Body>
                    {(detail.members || []).length === 0 ? (
                      <Table.Row>
                        <Table.Cell colSpan={4} textAlign="center" py={8}>
                          <VStack gap={2} color="fg.muted">
                            <FiAlertTriangle size={24} />
                            <Text fontSize="sm">No members found</Text>
                          </VStack>
                        </Table.Cell>
                      </Table.Row>
                    ) : (
                      (detail.members || []).map((m: GuildMember) => (
                        <Table.Row
                          key={m.player_id}
                          borderBottomWidth="1px"
                          borderColor="border"
                          _hover={{ bg: 'bg.subtle' }}
                          transition="all 0.15s"
                        >
                          <Table.Cell py={2} px={3}>
                            {m.player_name}
                          </Table.Cell>
                          <Table.Cell py={2} px={3}>
                            <Text
                              as="span"
                              fontSize="2xs"
                              bg="primary.subtle"
                              color="primary.DEFAULT"
                              borderWidth="1px"
                              borderColor="primary.DEFAULT/20"
                              borderRadius="full"
                              px={2}
                              py={0.5}
                            >
                              {m.role_name}
                            </Text>
                          </Table.Cell>
                          <Table.Cell py={2} px={3} fontSize="xs">
                            {m.online_status}
                          </Table.Cell>
                          <Table.Cell py={2} px={3}>
                            <HStack gap={1}>
                              <Button
                                variant="ghost"
                                size="xs"
                                fontSize="2xs"
                                color="primary.DEFAULT"
                                _hover={{ textDecoration: 'underline' }}
                                onClick={() => handleMemberAction('promote', m.player_id, 90)}
                              >
                                Promote
                              </Button>
                              <Button
                                variant="ghost"
                                size="xs"
                                fontSize="2xs"
                                color="fg.muted"
                                _hover={{ textDecoration: 'underline', color: 'fg' }}
                                onClick={() => handleMemberAction('demote', m.player_id, 50)}
                              >
                                Demote
                              </Button>
                              <Button
                                variant="ghost"
                                size="xs"
                                fontSize="2xs"
                                color="danger.DEFAULT"
                                _hover={{ textDecoration: 'underline' }}
                                onClick={() => handleMemberAction('remove', m.player_id)}
                              >
                                Remove
                              </Button>
                            </HStack>
                          </Table.Cell>
                        </Table.Row>
                      ))
                    )}
                  </Table.Body>
                </Table.Root>
              </Table.ScrollArea>
            </Box>

            <Box borderTopWidth="1px" borderColor="border" pt={4}>
              <Button
                variant="outline"
                size="xs"
                borderColor="danger.DEFAULT/30"
                color="danger.DEFAULT"
                bg="danger.subtle"
                borderRadius="lg"
                _hover={{ bg: 'danger.subtle/80' }}
                transition="all 0.15s"
                onClick={handleDisband}
              >
                <FiTrash2 size={12} style={{ marginRight: 6 }} />
                Disband Guild
              </Button>
            </Box>
          </VStack>
        )}
      </Modal>
    </Box>
  )
}
