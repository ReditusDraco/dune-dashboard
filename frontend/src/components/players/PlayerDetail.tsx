import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import useSWR from 'swr'
import {
  Box, Flex, Heading, Text, Button, Input, Select, Textarea,
  SimpleGrid, VStack, Table, Tabs, Card, createListCollection,
} from '@chakra-ui/react'
import { FiArrowLeft } from 'react-icons/fi'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import Badge from '../common/Badge'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

export default function PlayerDetail() {
  const { accountId } = useParams<{ accountId: string }>()
  const navigate = useNavigate()
  const { dispatch } = useApp()
  const [activeTab, setActiveTab] = useState('overview')

  const { data: detail } = useSWR(
    accountId ? `/players/${accountId}` : null,
    fetcher,
    { refreshInterval: 30000 }
  )

  const player = detail?.success ? detail.data : null

  const handleAction = async (endpoint: string, payload: any = {}) => {
    try {
      const res = await client.post(endpoint, payload)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Action successful', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Action failed', type: 'error' } })
    }
  }

  if (!player) {
    return <Text color="fg.muted">Loading player details...</Text>
  }

  return (
    <Box>
      <Flex mb={6}>
        <Button
          onClick={() => navigate('/players')}
          variant="ghost"
          size="sm"
          color="fg.muted"
          _hover={{ color: 'fg' }}
        >
          <FiArrowLeft style={{ marginRight: 6 }} /> Back to Players
        </Button>
      </Flex>

      <Flex align="center" justify="space-between" mb={6}>
        <Box>
          <Heading as="h1" fontFamily="Playfair Display, serif" fontSize="3xl" color="primary.DEFAULT">
            {player.character_name}
          </Heading>
          <Flex align="center" gap={2} mt={1}>
            <Badge
              label={player.online_status}
              variant={player.is_online ? 'success' : 'default'}
            />
            {player.faction_name && (
              <Text fontSize="sm" color="fg.muted">{player.faction_name}</Text>
            )}
            {player.tags?.map((tag: string) => (
              <Badge key={tag} label={tag} variant="warning" />
            ))}
          </Flex>
        </Box>
      </Flex>

      <Tabs.Root value={activeTab} onValueChange={(e) => setActiveTab(e.value)} mb={6}>
        <Tabs.List borderBottomWidth="1px" borderColor="border">
          {[
            { key: 'overview', label: 'Overview' },
            { key: 'inventory', label: 'Inventory' },
            { key: 'vehicles', label: 'Vehicles' },
            { key: 'buildings', label: 'Buildings' },
            { key: 'progression', label: 'Progression' },
            { key: 'actions', label: 'Actions' },
          ].map((t) => (
            <Tabs.Trigger
              key={t.key}
              value={t.key}
              px={4}
              py={2.5}
              fontSize="sm"
              fontWeight="medium"
              _selected={{ color: 'primary.DEFAULT', borderColor: 'primary.DEFAULT' }}
              color="fg.muted"
              borderBottomWidth="2px"
              borderColor="transparent"
            >
              {t.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="overview" pt={4}>
          <OverviewTab player={player} />
        </Tabs.Content>
        <Tabs.Content value="inventory" pt={4}>
          <InventoryTab player={player} />
        </Tabs.Content>
        <Tabs.Content value="vehicles" pt={4}>
          <VehiclesTab player={player} />
        </Tabs.Content>
        <Tabs.Content value="buildings" pt={4}>
          <BuildingsTab player={player} />
        </Tabs.Content>
        <Tabs.Content value="progression" pt={4}>
          <ProgressionTab player={player} />
        </Tabs.Content>
        <Tabs.Content value="actions" pt={4}>
          <ActionsTab player={player} onAction={handleAction} />
        </Tabs.Content>
      </Tabs.Root>
    </Box>
  )
}

function InfoRow({ label, value }: { label: string; value: any }) {
  return (
    <Box>
      <Text color="fg.muted" fontSize="xs" textTransform="uppercase" letterSpacing="wider">
        {label}
      </Text>
      <Text fontFamily="Roboto Mono, monospace">{value ?? 'N/A'}</Text>
    </Box>
  )
}

function OverviewTab({ player }: { player: any }) {
  const vitals = player.vitals || {}
  const currency = player.currency || []

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" mb={4}>
            Character Info
          </Heading>
          <SimpleGrid columns={2} gap={4} fontSize="sm">
            <InfoRow label="Account ID" value={player.account_id} />
            <InfoRow label="Controller ID" value={player.player_controller_id} />
            <InfoRow label="Pawn ID" value={player.player_pawn_id} />
            <InfoRow label="Email" value={player.account_email} />
            <InfoRow label="Funcom ID" value={player.funcom_id} />
            <InfoRow label="Map" value={player.map} />
            <InfoRow label="Life State" value={player.life_state} />
            <InfoRow label="Last Login" value={player.last_login_time} />
          </SimpleGrid>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" mb={4}>
            Vitals
          </Heading>
          <SimpleGrid columns={2} gap={4} fontSize="sm">
            <InfoRow label="Health" value={`${vitals.current_health ?? '?'}/${vitals.max_health ?? '?'}`} />
            <InfoRow label="Hydration" value={vitals.current_hydration ?? '?'} />
            <InfoRow label="Dehydration" value={vitals.dehydration_penalty ?? '?'} />
            <InfoRow label="Spice" value={vitals.current_spice ?? '?'} />
            <InfoRow label="Addiction" value={vitals.spice_addiction_level ?? '?'} />
            <InfoRow label="Tolerance" value={vitals.spice_tolerance ?? '?'} />
          </SimpleGrid>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" mb={4}>
            Currency
          </Heading>
          <VStack gap={2} align="stretch">
            {currency.length === 0 && <Text color="fg.muted" fontSize="sm">No currency data</Text>}
            {currency.map((c: any) => (
              <Flex key={c.currency_id} justify="space-between" fontSize="sm">
                <Text color="fg.muted">{c.currency_label}</Text>
                <Text fontFamily="Roboto Mono, monospace">{c.balance}</Text>
              </Flex>
            ))}
          </VStack>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" mb={4}>
            Landsraad
          </Heading>
          <SimpleGrid columns={2} gap={4} fontSize="sm">
            {player.landsraad ? (
              <>
                <InfoRow label="Daily Charges" value={player.landsraad.daily_reward_charges} />
                <InfoRow label="Last Term" value={player.landsraad.last_viewed_term_id} />
              </>
            ) : (
              <Text color="fg.muted">No landsraad data</Text>
            )}
          </SimpleGrid>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" mb={4}>
            Faction Reputation
          </Heading>
          <VStack gap={2} align="stretch">
            {(player.faction_reputation || []).length === 0 && <Text color="fg.muted" fontSize="sm">No reputation data</Text>}
            {(player.faction_reputation || []).map((r: any) => (
              <Flex key={r.faction_id} justify="space-between" fontSize="sm">
                <Text color="fg.muted">{r.faction_name || `Faction ${r.faction_id}`}</Text>
                <Text fontFamily="Roboto Mono, monospace">{r.reputation_amount}</Text>
              </Flex>
            ))}
          </VStack>
        </Card.Body>
      </Card.Root>
    </SimpleGrid>
  )
}

function InventoryTab({ player }: { player: any }) {
  const inventories = player.inventories || []
  const [selectedInv, setSelectedInv] = useState<any>(null)

  return (
    <Box>
      <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="xl" color="primary.DEFAULT" mb={4}>
        Inventories
      </Heading>
      <SimpleGrid columns={{ base: 1, md: 3 }} gap={4} mb={6}>
        {inventories.map((inv: any) => (
          <Box
            key={inv.inventory_id}
            as="button"
            onClick={() => setSelectedInv(inv)}
            textAlign="left"
            p={4}
            borderRadius="lg"
            borderWidth="1px"
            transition="colors"
            bg={selectedInv?.inventory_id === inv.inventory_id ? 'primary.subtle' : 'card.bg'}
            borderColor={selectedInv?.inventory_id === inv.inventory_id ? 'primary.DEFAULT' : 'border'}
            _hover={{ bg: 'bg.subtle' }}
          >
            <Text fontSize="sm" fontWeight="medium">{inv.inventory_type_label}</Text>
            <Text fontSize="xs" color="fg.muted" mt={1}>ID: {inv.inventory_id}</Text>
            <Text fontSize="xs" color="fg.muted">Items: {inv.items?.length || 0}</Text>
          </Box>
        ))}
      </SimpleGrid>

      {selectedInv && (
        <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
          <Card.Body p={5}>
            <Text fontWeight="medium" mb={3}>{selectedInv.inventory_type_label} Items</Text>
            <Box overflowX="auto">
              <Table.Root variant="line" size="sm">
                <Table.Header>
                  <Table.Row borderBottomWidth="1px" borderColor="border">
                    <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" px={3} py={2}>Item</Table.ColumnHeader>
                    <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" px={3} py={2}>Stack</Table.ColumnHeader>
                    <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" px={3} py={2}>Quality</Table.ColumnHeader>
                    <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" px={3} py={2}>Durability</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {(selectedInv.items || []).map((item: any, i: number) => (
                    <Table.Row key={i} borderBottomWidth="1px" borderColor="border" _last={{ borderBottomWidth: 0 }}>
                      <Table.Cell px={3} py={2}>{item.template_id}</Table.Cell>
                      <Table.Cell px={3} py={2} fontFamily="Roboto Mono, monospace">{item.stack_size}</Table.Cell>
                      <Table.Cell px={3} py={2} fontFamily="Roboto Mono, monospace">{item.quality_level}</Table.Cell>
                      <Table.Cell px={3} py={2} fontFamily="Roboto Mono, monospace">
                        {item.durability != null ? `${Math.round(item.durability)}/${Math.round(item.max_durability)}` : 'N/A'}
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Box>
          </Card.Body>
        </Card.Root>
      )}
    </Box>
  )
}

function VehiclesTab({ player }: { player: any }) {
  const vehicles = player.vehicles || []

  return (
    <Box>
      <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="xl" color="primary.DEFAULT" mb={4}>
        Vehicles
      </Heading>
      {vehicles.length === 0 ? (
        <Text color="fg.muted">No vehicles found.</Text>
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
          {vehicles.map((v: any) => (
            <Card.Root key={v.id} borderRadius="lg" boxShadow="card" bg="card.bg">
              <Card.Body p={4}>
                <Text fontWeight="medium">{v.display_name || v.class_name}</Text>
                <Text fontSize="xs" color="fg.muted" mt={1}>Map: {v.map || 'Unknown'}</Text>
                <Text fontSize="xs" color="fg.muted" fontFamily="Roboto Mono, monospace">ID: {v.id}</Text>
              </Card.Body>
            </Card.Root>
          ))}
        </SimpleGrid>
      )}
    </Box>
  )
}

function BuildingsTab({ player }: { player: any }) {
  const buildings = player.buildings || []
  const landclaims = player.landclaims || []

  return (
    <VStack gap={6} align="stretch">
      <Box>
        <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="xl" color="primary.DEFAULT" mb={4}>
          Buildings
        </Heading>
        {buildings.length === 0 ? (
          <Text color="fg.muted">No buildings found.</Text>
        ) : (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
            {buildings.map((b: any) => (
              <Card.Root key={b.id} borderRadius="lg" boxShadow="card" bg="card.bg">
                <Card.Body p={4}>
                  <Text fontWeight="medium">{b.class_name}</Text>
                  <Text fontSize="xs" color="fg.muted" mt={1}>Map: {b.map || 'Unknown'}</Text>
                  <Flex gap={2} mt={2}>
                    {b.is_powered && <Badge label="Powered" variant="success" />}
                    {b.power_level != null && <Badge label={`Power ${b.power_level}`} variant="default" />}
                  </Flex>
                </Card.Body>
              </Card.Root>
            ))}
          </SimpleGrid>
        )}
      </Box>

      <Box>
        <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="xl" color="primary.DEFAULT" mb={4}>
          Landclaims
        </Heading>
        {landclaims.length === 0 ? (
          <Text color="fg.muted">No landclaims found.</Text>
        ) : (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
            {landclaims.map((l: any) => (
              <Card.Root key={l.id} borderRadius="lg" boxShadow="card" bg="card.bg">
                <Card.Body p={4}>
                  <Text fontWeight="medium">{l.class_name}</Text>
                  <Text fontSize="xs" color="fg.muted" mt={1}>Map: {l.map || 'Unknown'}</Text>
                </Card.Body>
              </Card.Root>
            ))}
          </SimpleGrid>
        )}
      </Box>
    </VStack>
  )
}

function ProgressionTab({ player }: { player: any }) {
  const specs = player.specialization || []
  const keystones = player.keystones || []

  return (
    <VStack gap={6} align="stretch">
      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" mb={4}>
            Specialization Tracks
          </Heading>
          {specs.length === 0 ? (
            <Text color="fg.muted">No specialization data.</Text>
          ) : (
            <VStack gap={3} align="stretch">
              {specs.map((s: any, i: number) => (
                <Flex key={i} justify="space-between" align="center">
                  <Text fontSize="sm" color="fg.muted">{s.track_type}</Text>
                  <Flex align="center" gap={4}>
                    <Text fontSize="xs" color="fg.muted">XP: {s.xp_amount}</Text>
                    <Badge label={`Lv ${s.level}`} variant="default" />
                  </Flex>
                </Flex>
              ))}
            </VStack>
          )}
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <Heading as="h3" fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" mb={4}>
            Keystones
          </Heading>
          {keystones.length === 0 ? (
            <Text color="fg.muted">No keystones.</Text>
          ) : (
            <Flex wrap="wrap" gap={2}>
              {keystones.map((k: any) => (
                <Badge key={k.id} label={k.name} variant="default" />
              ))}
            </Flex>
          )}
        </Card.Body>
      </Card.Root>
    </VStack>
  )
}

const currencyCollection = createListCollection({
  items: [
    { value: '0', label: 'Solari Credits' },
    { value: '1', label: 'House Script' },
    { value: '2', label: 'Spice' },
  ],
})

function ActionsTab({ player, onAction }: { player: any; onAction: (endpoint: string, payload?: any) => Promise<void> }) {
  const accountId = player.account_id
  const [newName, setNewName] = useState('')
  const [currencyForm, setCurrencyForm] = useState({ currency_id: '0', amount: '' })
  const [vitalsForm, setVitalsForm] = useState({ health: '', hydration: '', spice: '' })
  const [teleportForm, setTeleportForm] = useState({ partition: '', x: '', y: '', z: '' })
  const [banReason, setBanReason] = useState('')
  const [banDuration, setBanDuration] = useState('0')

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <ActionCard title="Currency">
        <VStack gap={2} align="stretch">
          <Select.Root
            collection={currencyCollection}
            value={[currencyForm.currency_id]}
            onValueChange={(e) => setCurrencyForm({ ...currencyForm, currency_id: e.value[0] })}
          >
            <Select.Trigger bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm">
              <Select.ValueText />
            </Select.Trigger>
            <Select.Content>
              {currencyCollection.items.map((item) => (
                <Select.Item item={item} key={item.value}>
                  {item.label}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Root>
          <Input
            type="number"
            value={currencyForm.amount}
            onChange={(e) => setCurrencyForm({ ...currencyForm, amount: e.target.value })}
            placeholder="Amount"
            bg="card.bg"
            borderColor="border"
            borderRadius="md"
            fontSize="sm"
          />
          <Flex gap={2}>
            <Button
              onClick={() => onAction('/currency/adjust', { player_id: accountId, currency_id: parseInt(currencyForm.currency_id), amount: parseFloat(currencyForm.amount) })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="primary.DEFAULT"
              borderColor="primary.DEFAULT"
            >
              Adjust
            </Button>
            <Button
              onClick={() => onAction('/currency/set', { player_id: accountId, currency_id: parseInt(currencyForm.currency_id), amount: parseFloat(currencyForm.amount) })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="primary.DEFAULT"
              borderColor="primary.DEFAULT"
            >
              Set Exact
            </Button>
          </Flex>
        </VStack>
      </ActionCard>

      <ActionCard title="Vitals">
        <VStack gap={2} align="stretch">
          <Input
            type="number"
            value={vitalsForm.health}
            onChange={(e) => setVitalsForm({ ...vitalsForm, health: e.target.value })}
            placeholder="Health"
            bg="card.bg"
            borderColor="border"
            borderRadius="md"
            fontSize="sm"
          />
          <Input
            type="number"
            value={vitalsForm.hydration}
            onChange={(e) => setVitalsForm({ ...vitalsForm, hydration: e.target.value })}
            placeholder="Hydration"
            bg="card.bg"
            borderColor="border"
            borderRadius="md"
            fontSize="sm"
          />
          <Input
            type="number"
            value={vitalsForm.spice}
            onChange={(e) => setVitalsForm({ ...vitalsForm, spice: e.target.value })}
            placeholder="Spice"
            bg="card.bg"
            borderColor="border"
            borderRadius="md"
            fontSize="sm"
          />
          <Button
            onClick={() => onAction('/vitals/set', { player_id: accountId, health: parseFloat(vitalsForm.health) || undefined, hydration: parseFloat(vitalsForm.hydration) || undefined, spice: parseFloat(vitalsForm.spice) || undefined })}
            size="xs"
            variant="outline"
            borderRadius="md"
            color="primary.DEFAULT"
            borderColor="primary.DEFAULT"
          >
            Set Vitals
          </Button>
        </VStack>
      </ActionCard>

      <ActionCard title="Teleport">
        <VStack gap={2} align="stretch">
          <Input
            value={teleportForm.partition}
            onChange={(e) => setTeleportForm({ ...teleportForm, partition: e.target.value })}
            placeholder="Partition ID"
            bg="card.bg"
            borderColor="border"
            borderRadius="md"
            fontSize="sm"
          />
          <Flex gap={2}>
            <Input
              type="number"
              value={teleportForm.x}
              onChange={(e) => setTeleportForm({ ...teleportForm, x: e.target.value })}
              placeholder="X"
              bg="card.bg"
              borderColor="border"
              borderRadius="md"
              fontSize="sm"
            />
            <Input
              type="number"
              value={teleportForm.y}
              onChange={(e) => setTeleportForm({ ...teleportForm, y: e.target.value })}
              placeholder="Y"
              bg="card.bg"
              borderColor="border"
              borderRadius="md"
              fontSize="sm"
            />
            <Input
              type="number"
              value={teleportForm.z}
              onChange={(e) => setTeleportForm({ ...teleportForm, z: e.target.value })}
              placeholder="Z"
              bg="card.bg"
              borderColor="border"
              borderRadius="md"
              fontSize="sm"
            />
          </Flex>
          <Button
            onClick={() => onAction('/teleport', { fls_id: accountId, partition_id: teleportForm.partition, x: parseFloat(teleportForm.x) || 0, y: parseFloat(teleportForm.y) || 0, z: parseFloat(teleportForm.z) || 0 })}
            size="xs"
            variant="outline"
            borderRadius="md"
            color="primary.DEFAULT"
            borderColor="primary.DEFAULT"
          >
            Teleport
          </Button>
        </VStack>
      </ActionCard>

      <ActionCard title="Character">
        <VStack gap={2} align="stretch">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="New character name"
            bg="card.bg"
            borderColor="border"
            borderRadius="md"
            fontSize="sm"
          />
          <Flex wrap="wrap" gap={2}>
            <Button
              onClick={() => onAction(`/characters/${accountId}/name`, { name: newName })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="primary.DEFAULT"
              borderColor="primary.DEFAULT"
            >
              Rename
            </Button>
            <Button
              onClick={() => onAction(`/accounts/${accountId}/demo`, { demo: true })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="warning.DEFAULT"
              borderColor="warning.DEFAULT"
            >
              Set Demo
            </Button>
            <Button
              onClick={() => onAction(`/accounts/${accountId}/demo`, { demo: false })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="warning.DEFAULT"
              borderColor="warning.DEFAULT"
            >
              Clear Demo
            </Button>
            <Button
              onClick={() => {
                if (confirm('Delete this character? This cannot be undone.')) {
                  onAction(`/characters/${accountId}`, {})
                }
              }}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="danger.DEFAULT"
              borderColor="danger.DEFAULT"
            >
              Delete Character
            </Button>
            <Button
              onClick={() => {
                if (confirm('Delete this entire account? This cannot be undone.')) {
                  onAction(`/accounts/${accountId}`, {})
                }
              }}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="danger.DEFAULT"
              borderColor="danger.DEFAULT"
            >
              Delete Account
            </Button>
          </Flex>
        </VStack>
      </ActionCard>

      <ActionCard title="Moderation">
        <VStack gap={2} align="stretch">
          <Input
            value={banReason}
            onChange={(e) => setBanReason(e.target.value)}
            placeholder="Ban reason"
            bg="card.bg"
            borderColor="border"
            borderRadius="md"
            fontSize="sm"
          />
          <Input
            type="number"
            value={banDuration}
            onChange={(e) => setBanDuration(e.target.value)}
            placeholder="Duration (hours, 0 = permanent)"
            bg="card.bg"
            borderColor="border"
            borderRadius="md"
            fontSize="sm"
          />
          <Flex wrap="wrap" gap={2}>
            <Button
              onClick={() => onAction(`/players/${accountId}/ban`, { reason: banReason, duration_hours: parseInt(banDuration) || 0 })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="danger.DEFAULT"
              borderColor="danger.DEFAULT"
            >
              Ban Player
            </Button>
            <Button
              onClick={() => onAction(`/players/${accountId}/unban`, {})}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="success.DEFAULT"
              borderColor="success.DEFAULT"
            >
              Unban Player
            </Button>
            <Button
              onClick={() => onAction(`/players/${accountId}/kick`, { reason: banReason })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="warning.DEFAULT"
              borderColor="warning.DEFAULT"
            >
              Kick Player
            </Button>
          </Flex>
        </VStack>
      </ActionCard>
    </SimpleGrid>
  )
}

function ActionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
      <Card.Body p={5}>
        <Text fontWeight="medium" mb={3}>{title}</Text>
        {children}
      </Card.Body>
    </Card.Root>
  )
}
