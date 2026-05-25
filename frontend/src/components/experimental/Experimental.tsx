import { useState } from 'react'
import {
  Box, Flex, Text, Heading, Tabs, Card, Button,
  Input, Textarea, Select, SimpleGrid, VStack, HStack,
  Field, Spinner, Badge as ChakraBadge, Switch, Separator,
  NumberInput, Table, createListCollection,
} from '@chakra-ui/react'
import {
  FiSend, FiUsers, FiSearch, FiRefreshCw, FiDollarSign,
  FiFlag, FiShield, FiBox, FiMap, FiDatabase,
  FiTerminal, FiPlay, FiAlertTriangle, FiTrash2,
  FiTag, FiUser, FiGlobe, FiRadio, FiCode,
} from 'react-icons/fi'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

const apiPost = async (url: string, body?: unknown) => {
  const res = await client.post(url, body)
  return res.data
}

const apiGet = async (url: string) => {
  const res = await client.get(url)
  return res.data
}

export default function Experimental() {
  const { dispatch } = useApp()
  const [tab, setTab] = useState('broadcast')
  const [loading, setLoading] = useState<string | null>(null)

  const doAction = async (url: string, body: unknown, label: string) => {
    setLoading(label)
    try {
      const result = await apiPost(url, body)
      if (result.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: `${label} succeeded`, type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: result.error || `${label} failed`, type: 'error' } })
      }
      return result
    } catch {
      dispatch({ type: 'ADD_TOAST', payload: { message: `${label} failed`, type: 'error' } })
    } finally {
      setLoading(null)
    }
  }

  return (
    <Box>
      <Flex align="center" gap={3} mb={2}>
        <Heading as="h1" fontSize="3xl" fontFamily="Playfair Display, serif" color="primary.DEFAULT">
          Experimental
        </Heading>
        <ChakraBadge variant="subtle" bg="warning.subtle" color="warning.DEFAULT" borderRadius="full" px={3} py={1}>
          <FiAlertTriangle size={12} style={{ display: 'inline', marginRight: '4px' }} />
          Testing Area
        </ChakraBadge>
      </Flex>
      <Text color="fg.muted" fontSize="sm" mb={6}>
        Experimental tools for RMQ API testing. Features are unstable and subject to change.
      </Text>

      <Tabs.Root value={tab} onValueChange={(e) => setTab(e.value)} variant="line" mb={6}>
        <Tabs.List borderBottomWidth="1px" borderColor="border" gap={0} overflowX="auto">
          {[
            { value: 'broadcast', label: 'Broadcast', icon: FiRadio },
            { value: 'players', label: 'Players', icon: FiUsers },
            { value: 'guilds', label: 'Guilds', icon: FiShield },
            { value: 'world', label: 'World', icon: FiGlobe },
            { value: 'functions', label: 'Functions', icon: FiCode },
            { value: 'query', label: 'Raw Query', icon: FiDatabase },
          ].map(({ value, label, icon: Icon }) => (
            <Tabs.Trigger
              key={value}
              value={value}
              px={3} py={2.5} fontSize="sm" fontWeight="medium"
              color="fg.muted"
              borderBottom="2px solid transparent"
              _selected={{ color: 'primary.DEFAULT', borderColor: 'primary.DEFAULT' }}
              transition="all 0.15s"
              gap={1.5}
            >
              <Icon size={14} />
              {label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="broadcast" pt={4}>
          <BroadcastTab dispatch={dispatch} />
        </Tabs.Content>

        <Tabs.Content value="players" pt={4}>
          <PlayersTab dispatch={dispatch} loading={loading} setLoading={setLoading} />
        </Tabs.Content>

        <Tabs.Content value="guilds" pt={4}>
          <GuildsTab dispatch={dispatch} loading={loading} setLoading={setLoading} />
        </Tabs.Content>

        <Tabs.Content value="world" pt={4}>
          <WorldTab dispatch={dispatch} loading={loading} setLoading={setLoading} />
        </Tabs.Content>

        <Tabs.Content value="functions" pt={4}>
          <FunctionsTab dispatch={dispatch} loading={loading} setLoading={setLoading} />
        </Tabs.Content>

        <Tabs.Content value="query" pt={4}>
          <RawQueryTab dispatch={dispatch} loading={loading} setLoading={setLoading} />
        </Tabs.Content>
      </Tabs.Root>
    </Box>
  )
}

function CardSection({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card">
      <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={3}>
        <Flex align="center" gap={2}>
          <Icon size={16} />
          <Text fontFamily="Playfair Display, serif" fontSize="md" color="primary.DEFAULT" fontWeight="semibold">
            {title}
          </Text>
        </Flex>
      </Card.Header>
      <Card.Body p={5}>
        {children}
      </Card.Body>
    </Card.Root>
  )
}

function BroadcastTab({ dispatch }: { dispatch: ReturnType<typeof useApp>['dispatch'] }) {
  const [title, setTitle] = useState('Server Notice')
  const [message, setMessage] = useState('')
  const [duration, setDuration] = useState(30)
  const [sending, setSending] = useState(false)

  const send = async () => {
    setSending(true)
    try {
      const res = await apiPost('/admin-experimental/broadcast', { title, message, duration })
      dispatch({ type: 'ADD_TOAST', payload: { message: res.success ? 'Broadcast sent' : (res.error || 'Failed'), type: res.success ? 'success' : 'error' } })
    } catch {
      dispatch({ type: 'ADD_TOAST', payload: { message: 'Broadcast failed', type: 'error' } })
    } finally {
      setSending(false)
    }
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <CardSection title="Send Broadcast" icon={FiRadio}>
        <Text fontSize="sm" color="fg.muted" mb={4}>Send a notification to all connected players via RabbitMQ heartbeats exchange.</Text>
        <VStack align="stretch" gap={4}>
          <Field.Root>
            <Field.Label fontSize="sm" color="fg">Title</Field.Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Server Notice" />
          </Field.Root>
          <Field.Root>
            <Field.Label fontSize="sm" color="fg">Message</Field.Label>
            <Textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Broadcast message..." rows={3} />
          </Field.Root>
          <Field.Root>
            <Field.Label fontSize="sm" color="fg">Duration (seconds)</Field.Label>
            <NumberInput.Root value={String(duration)} onValueChange={(v) => setDuration(Number(v.value))} min={5} max={300}>
              <NumberInput.Input />
            </NumberInput.Root>
          </Field.Root>
          <Button onClick={send} loading={sending}><FiSend size={14} /> 
            Send Broadcast
          </Button>
        </VStack>
      </CardSection>
    </SimpleGrid>
  )
}

function PlayersTab({ dispatch, loading, setLoading }: {
  dispatch: ReturnType<typeof useApp>['dispatch']
  loading: string | null
  setLoading: (v: string | null) => void
}) {
  const [searchTerm, setSearchTerm] = useState('')
  const [searchResults, setSearchResults] = useState<any>(null)
  const [onlinePlayers, setOnlinePlayers] = useState<any>(null)
  const [currencyPid, setCurrencyPid] = useState('')
  const [currencyCid, setCurrencyCid] = useState('0')
  const [currencyDelta, setCurrencyDelta] = useState('1000')
  const [currencyResult, setCurrencyResult] = useState<any>(null)
  const [factionPid, setFactionPid] = useState('')
  const [factionId, setFactionId] = useState('')
  const [teleportPid, setTeleportPid] = useState('')
  const [teleportX, setTeleportX] = useState('')
  const [teleportY, setTeleportY] = useState('')
  const [teleportZ, setTeleportZ] = useState('')
  const [tagPid, setTagPid] = useState('')
  const [tagKey, setTagKey] = useState('')
  const [tagValue, setTagValue] = useState('')
  const [tagResult, setTagResult] = useState<any>(null)
  const [cheaterPid, setCheaterPid] = useState('')
  const [cheaterReason, setCheaterReason] = useState('')

  const search = async () => {
    setLoading('search')
    try {
      const res = await apiPost('/admin-experimental/search-players', { term: searchTerm })
      setSearchResults(res)
    } finally { setLoading(null) }
  }

  const loadOnline = async () => {
    setLoading('online')
    try {
      const res = await apiGet('/admin-experimental/online-players')
      setOnlinePlayers(res)
    } finally { setLoading(null) }
  }

  const adjustCurrency = async () => {
    const res = await apiPost('/admin-experimental/adjust-currency', {
      player_id: Number(currencyPid),
      currency_id: Number(currencyCid),
      delta: Number(currencyDelta),
    })
    if (res.success) dispatch({ type: 'ADD_TOAST', payload: { message: 'Currency adjusted', type: 'success' } })
  }

  const viewCurrency = async () => {
    const res = await apiPost('/admin-experimental/currency-balances', { player_id: Number(currencyPid) })
    setCurrencyResult(res)
  }

  const changeFaction = async () => {
    await apiPost('/admin-experimental/change-faction', { player_id: Number(factionPid), faction_id: Number(factionId) })
    dispatch({ type: 'ADD_TOAST', payload: { message: 'Faction change requested', type: 'info' } })
  }

  const doTeleport = async () => {
    await apiPost('/admin-experimental/teleport', {
      player_id: Number(teleportPid),
      x: Number(teleportX),
      y: Number(teleportY),
      z: Number(teleportZ),
    })
    dispatch({ type: 'ADD_TOAST', payload: { message: 'Teleport requested', type: 'info' } })
  }

  const getTags = async () => {
    const res = await apiPost('/admin-experimental/player-tags', { player_id: Number(tagPid) })
    setTagResult(res)
  }

  const setTag = async () => {
    const res = await apiPost('/admin-experimental/player-tags', {
      player_id: Number(tagPid),
      key: tagKey,
      value: tagValue,
      action: 'set',
    })
    dispatch({ type: 'ADD_TOAST', payload: { message: res.success ? 'Tag set' : 'Failed', type: res.success ? 'success' : 'error' } })
  }

  const flagCheater = async () => {
    const res = await apiPost('/admin-experimental/flag-cheater', {
      player_id: Number(cheaterPid),
      reason: cheaterReason,
    })
    dispatch({ type: 'ADD_TOAST', payload: { message: res.success ? 'Player flagged' : 'Failed', type: res.success ? 'success' : 'error' } })
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <CardSection title="Search Players" icon={FiSearch}>
        <Flex gap={2} mb={4}>
          <Input value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Character name..." />
          <Button onClick={search} loading={loading === 'search'}><FiSearch size={14} /> Search</Button>
        </Flex>
        {searchResults && (
          <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="300px">
            {JSON.stringify(searchResults, null, 2)}
          </Box>
        )}
      </CardSection>

      <CardSection title="Online Players" icon={FiUsers}>
        <Button onClick={loadOnline} loading={loading === 'online'} mb={4}><FiRefreshCw size={14} /> Refresh</Button>
        {onlinePlayers && (
          <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="300px">
            {JSON.stringify(onlinePlayers, null, 2)}
          </Box>
        )}
      </CardSection>

      <CardSection title="Adjust Currency" icon={FiDollarSign}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Player Controller ID</Field.Label>
            <Input value={currencyPid} onChange={(e) => setCurrencyPid(e.target.value)} placeholder="e.g. 81" />
          </Field.Root>
          <Flex gap={3}>
            <Box flex={1}>
              <Field.Root>
                <Field.Label fontSize="sm">Currency</Field.Label>
                <Select.Root
                  value={[currencyCid]}
                  onValueChange={(e) => setCurrencyCid(e.value[0])}
                  collection={createListCollection({ items: [
                    { value: '0', label: 'Solari Credits' },
                    { value: '1', label: 'House Script' },
                    { value: '2', label: 'Spice' },
                  ]})}
                  size="sm"
                >
                  <Select.Trigger>
                    <Select.ValueText placeholder="Select currency" />
                  </Select.Trigger>
                  <Select.Content>
                    {createListCollection({ items: [
                      { value: '0', label: 'Solari Credits' },
                      { value: '1', label: 'House Script' },
                      { value: '2', label: 'Spice' },
                    ]}).items.map((item) => (
                      <Select.Item key={item.value} item={item}>
                        {item.label}
                      </Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              </Field.Root>
            </Box>
            <Box flex={1}>
              <Field.Root>
                <Field.Label fontSize="sm">Delta</Field.Label>
                <Input value={currencyDelta} onChange={(e) => setCurrencyDelta(e.target.value)} type="number" />
              </Field.Root>
            </Box>
          </Flex>
          <Flex gap={2}>
            <Button onClick={adjustCurrency}><FiDollarSign size={14} /> Apply</Button>
            <Button variant="outline" onClick={viewCurrency}><FiSearch size={14} /> View Balances</Button>
          </Flex>
          {currencyResult && (
            <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="200px">
              {JSON.stringify(currencyResult, null, 2)}
            </Box>
          )}
        </VStack>
      </CardSection>

      <CardSection title="Change Faction" icon={FiFlag}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Player ID</Field.Label>
            <Input value={factionPid} onChange={(e) => setFactionPid(e.target.value)} placeholder="e.g. 81" />
          </Field.Root>
          <Field.Root>
            <Field.Label fontSize="sm">New Faction ID</Field.Label>
            <Input value={factionId} onChange={(e) => setFactionId(e.target.value)} placeholder="Faction ID" />
          </Field.Root>
          <Button onClick={changeFaction}><FiFlag size={14} /> Change Faction</Button>
        </VStack>
      </CardSection>

      <CardSection title="Teleport Player" icon={FiMap}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Player ID</Field.Label>
            <Input value={teleportPid} onChange={(e) => setTeleportPid(e.target.value)} placeholder="Player ID" />
          </Field.Root>
          <SimpleGrid columns={3} gap={3}>
            <Field.Root>
              <Field.Label fontSize="sm">X</Field.Label>
              <Input value={teleportX} onChange={(e) => setTeleportX(e.target.value)} placeholder="X" />
            </Field.Root>
            <Field.Root>
              <Field.Label fontSize="sm">Y</Field.Label>
              <Input value={teleportY} onChange={(e) => setTeleportY(e.target.value)} placeholder="Y" />
            </Field.Root>
            <Field.Root>
              <Field.Label fontSize="sm">Z</Field.Label>
              <Input value={teleportZ} onChange={(e) => setTeleportZ(e.target.value)} placeholder="Z" />
            </Field.Root>
          </SimpleGrid>
          <Button onClick={doTeleport}><FiMap size={14} /> Teleport</Button>
        </VStack>
      </CardSection>

      <CardSection title="Player Tags" icon={FiTag}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Player ID</Field.Label>
            <Input value={tagPid} onChange={(e) => setTagPid(e.target.value)} placeholder="Player ID" />
          </Field.Root>
          <Flex gap={3}>
            <Box flex={1}>
              <Field.Root>
                <Field.Label fontSize="sm">Key</Field.Label>
                <Input value={tagKey} onChange={(e) => setTagKey(e.target.value)} placeholder="Tag key" />
              </Field.Root>
            </Box>
            <Box flex={1}>
              <Field.Root>
                <Field.Label fontSize="sm">Value</Field.Label>
                <Input value={tagValue} onChange={(e) => setTagValue(e.target.value)} placeholder="Tag value" />
              </Field.Root>
            </Box>
          </Flex>
          <Flex gap={2}>
            <Button onClick={getTags}><FiSearch size={14} /> Get Tags</Button>
            <Button onClick={setTag}><FiTag size={14} /> Set Tag</Button>
          </Flex>
          {tagResult && (
            <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="200px">
              {JSON.stringify(tagResult, null, 2)}
            </Box>
          )}
        </VStack>
      </CardSection>

      <CardSection title="Flag Cheater" icon={FiAlertTriangle}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Player ID</Field.Label>
            <Input value={cheaterPid} onChange={(e) => setCheaterPid(e.target.value)} placeholder="Player ID" />
          </Field.Root>
          <Field.Root>
            <Field.Label fontSize="sm">Reason</Field.Label>
            <Textarea value={cheaterReason} onChange={(e) => setCheaterReason(e.target.value)} placeholder="Reason for flagging..." rows={2} />
          </Field.Root>
          <Button onClick={flagCheater}><FiFlag size={14} /> Flag Cheater</Button>
        </VStack>
      </CardSection>
    </SimpleGrid>
  )
}

function GuildsTab({ dispatch, loading, setLoading }: {
  dispatch: ReturnType<typeof useApp>['dispatch']
  loading: string | null
  setLoading: (v: string | null) => void
}) {
  const [guildsData, setGuildsData] = useState<any>(null)
  const [guildId, setGuildId] = useState('')
  const [guildInfo, setGuildInfo] = useState<any>(null)
  const [disbandId, setDisbandId] = useState('')
  const [removeGuildId, setRemoveGuildId] = useState('')
  const [removePlayerId, setRemovePlayerId] = useState('')

  const listGuilds = async () => {
    setLoading('guilds')
    try {
      const res = await apiGet('/admin-experimental/guilds')
      setGuildsData(res)
    } finally { setLoading(null) }
  }

  const getGuildData = async () => {
    const res = await apiPost('/admin-experimental/guild-data', { guild_id: Number(guildId) })
    setGuildInfo(res)
  }

  const disbandGuild = async () => {
    const res = await apiPost('/admin-experimental/disband-guild', { guild_id: Number(disbandId) })
    dispatch({ type: 'ADD_TOAST', payload: { message: res.success ? 'Guild disbanded' : (res.error || 'Failed'), type: res.success ? 'success' : 'error' } })
  }

  const removeMember = async () => {
    const res = await apiPost('/admin-experimental/remove-guild-member', {
      guild_id: Number(removeGuildId),
      player_id: Number(removePlayerId),
    })
    dispatch({ type: 'ADD_TOAST', payload: { message: res.success ? 'Member removed' : (res.error || 'Failed'), type: res.success ? 'success' : 'error' } })
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <CardSection title="Guild List" icon={FiShield}>
        <Button onClick={listGuilds} loading={loading === 'guilds'} mb={4}><FiRefreshCw size={14} /> Load Guilds</Button>
        {guildsData && (
          <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="400px">
            {JSON.stringify(guildsData, null, 2)}
          </Box>
        )}
      </CardSection>

      <CardSection title="Guild Info" icon={FiSearch}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Guild ID</Field.Label>
            <Input value={guildId} onChange={(e) => setGuildId(e.target.value)} placeholder="Guild ID" />
          </Field.Root>
          <Button onClick={getGuildData}><FiSearch size={14} /> Get Info</Button>
          {guildInfo && (
            <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="200px">
              {JSON.stringify(guildInfo, null, 2)}
            </Box>
          )}
        </VStack>
      </CardSection>

      <CardSection title="Disband Guild" icon={FiTrash2}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Guild ID</Field.Label>
            <Input value={disbandId} onChange={(e) => setDisbandId(e.target.value)} placeholder="Guild ID" />
          </Field.Root>
          <Button onClick={disbandGuild}><FiTrash2 size={14} /> Disband Guild</Button>
        </VStack>
      </CardSection>

      <CardSection title="Remove Guild Member" icon={FiUser}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Guild ID</Field.Label>
            <Input value={removeGuildId} onChange={(e) => setRemoveGuildId(e.target.value)} placeholder="Guild ID" />
          </Field.Root>
          <Field.Root>
            <Field.Label fontSize="sm">Player ID</Field.Label>
            <Input value={removePlayerId} onChange={(e) => setRemovePlayerId(e.target.value)} placeholder="Player ID" />
          </Field.Root>
          <Button onClick={removeMember}><FiUser size={14} /> Remove Member</Button>
        </VStack>
      </CardSection>
    </SimpleGrid>
  )
}

function WorldTab({ dispatch, loading, setLoading }: {
  dispatch: ReturnType<typeof useApp>['dispatch']
  loading: string | null
  setLoading: (v: string | null) => void
}) {
  const [partitionsData, setPartitionsData] = useState<any>(null)
  const [spiceData, setSpiceData] = useState<any>(null)
  const [vendorResult, setVendorResult] = useState<any>(null)
  const [taxResult, setTaxResult] = useState<any>(null)

  const loadPartitions = async () => {
    setLoading('partitions')
    try { const r = await apiGet('/admin-experimental/partitions'); setPartitionsData(r) } finally { setLoading(null) }
  }

  const cleanVendor = async () => {
    const r = await apiPost('/admin-experimental/clean-vendor-stock', {})
    setVendorResult(r)
    dispatch({ type: 'ADD_TOAST', payload: { message: r.success ? 'Vendor stock cleaned' : 'Failed', type: r.success ? 'success' : 'error' } })
  }

  const getTaxInvoices = async () => {
    const r = await apiPost('/admin-experimental/tax-invoices', {})
    setTaxResult(r)
  }

  const controlSpice = async (action: string) => {
    const r = await apiPost('/admin-experimental/spice', { action })
    setSpiceData(r)
    dispatch({ type: 'ADD_TOAST', payload: { message: r.success ? 'Spice action completed' : 'Failed', type: r.success ? 'success' : 'error' } })
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <CardSection title="Partitions" icon={FiMap}>
        <Button onClick={loadPartitions} loading={loading === 'partitions'} mb={4}><FiRefreshCw size={14} /> Load</Button>
        {partitionsData && (
          <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="300px">
            {JSON.stringify(partitionsData, null, 2)}
          </Box>
        )}
      </CardSection>

      <CardSection title="Spice Fields" icon={FiBox}>
        <Flex gap={2} mb={4} wrap="wrap">
          <Button size="sm" onClick={() => controlSpice('list')}>List</Button>
          <Button size="sm" onClick={() => controlSpice('reset')}>Reset</Button>
          <Button size="sm" onClick={() => controlSpice('regenerate')}>Regenerate</Button>
        </Flex>
        {spiceData && (
          <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="200px">
            {JSON.stringify(spiceData, null, 2)}
          </Box>
        )}
      </CardSection>

      <CardSection title="Vendor Stock" icon={FiBox}>
        <Text fontSize="sm" color="fg.muted" mb={4}>Clean all vendor stock entries.</Text>
        <Button onClick={cleanVendor}><FiRefreshCw size={14} /> Clean Stock</Button>
        {vendorResult && (
          <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="200px" mt={4}>
            {JSON.stringify(vendorResult, null, 2)}
          </Box>
        )}
      </CardSection>

      <CardSection title="Tax Invoices" icon={FiDollarSign}>
        <Text fontSize="sm" color="fg.muted" mb={4}>View tax invoice data.</Text>
        <Button onClick={getTaxInvoices} mb={4}><FiSearch size={14} /> Load Invoices</Button>
        {taxResult && (
          <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="300px">
            {JSON.stringify(taxResult, null, 2)}
          </Box>
        )}
      </CardSection>
    </SimpleGrid>
  )
}

function FunctionsTab({ dispatch, loading, setLoading }: {
  dispatch: ReturnType<typeof useApp>['dispatch']
  loading: string | null
  setLoading: (v: string | null) => void
}) {
  const [functionsData, setFunctionsData] = useState<any>(null)
  const [funcName, setFuncName] = useState('')
  const [funcInfo, setFuncInfo] = useState<any>(null)
  const [funcArgs, setFuncArgs] = useState('{}')
  const [execResult, setExecResult] = useState<any>(null)

  const listFunctions = async () => {
    setLoading('functions')
    try { const r = await apiGet('/admin-experimental/functions'); setFunctionsData(r) } finally { setLoading(null) }
  }

  const getFunctionInfo = async () => {
    const r = await apiGet(`/admin-experimental/functions/${funcName}`)
    setFuncInfo(r)
  }

  const executeFunction = async () => {
    setLoading('exec')
    try {
      const r = await apiPost(`/admin-experimental/functions/${funcName}/execute`, JSON.parse(funcArgs))
      setExecResult(r)
      dispatch({ type: 'ADD_TOAST', payload: { message: r.success ? 'Executed' : (r.error || 'Failed'), type: r.success ? 'success' : 'error' } })
    } finally { setLoading(null) }
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <CardSection title="Stored Procedures" icon={FiCode}>
        <Button onClick={listFunctions} loading={loading === 'functions'} mb={4}><FiRefreshCw size={14} /> Load Functions</Button>
        {functionsData && (
          <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="400px">
            {JSON.stringify(functionsData, null, 2)}
          </Box>
        )}
      </CardSection>

      <CardSection title="Execute Function" icon={FiPlay}>
        <VStack align="stretch" gap={3}>
          <Field.Root>
            <Field.Label fontSize="sm">Function Name</Field.Label>
            <Input value={funcName} onChange={(e) => setFuncName(e.target.value)} placeholder="schema.function_name" />
          </Field.Root>
          <Button variant="outline" onClick={getFunctionInfo}><FiSearch size={14} /> Get Info</Button>
          {funcInfo && (
            <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="150px">
              {JSON.stringify(funcInfo, null, 2)}
            </Box>
          )}
          <Field.Root>
            <Field.Label fontSize="sm">Arguments (JSON array)</Field.Label>
            <Textarea value={funcArgs} onChange={(e) => setFuncArgs(e.target.value)} rows={3} fontFamily="Roboto Mono, monospace" fontSize="xs" />
          </Field.Root>
          <Button onClick={executeFunction} loading={loading === 'exec'}><FiPlay size={14} /> Execute</Button>
          {execResult && (
            <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={3} borderRadius="md" overflow="auto" maxH="300px">
              {JSON.stringify(execResult, null, 2)}
            </Box>
          )}
        </VStack>
      </CardSection>
    </SimpleGrid>
  )
}

function RawQueryTab({ dispatch, loading, setLoading }: {
  dispatch: ReturnType<typeof useApp>['dispatch']
  loading: string | null
  setLoading: (v: string | null) => void
}) {
  const [sql, setSql] = useState('')
  const [result, setResult] = useState<any>(null)

  const execute = async () => {
    setLoading('query')
    try {
      const r = await apiPost('/admin-experimental/execute', { query: sql })
      setResult(r)
    } catch {
      dispatch({ type: 'ADD_TOAST', payload: { message: 'Query failed', type: 'error' } })
    } finally { setLoading(null) }
  }

  return (
    <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card">
      <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={3}>
        <Flex align="center" gap={2}>
          <FiDatabase size={16} />
          <Text fontFamily="Playfair Display, serif" fontSize="md" color="primary.DEFAULT" fontWeight="semibold">
            Raw SQL Query
          </Text>
        </Flex>
      </Card.Header>
      <Card.Body p={5}>
        <Text fontSize="sm" color="fg.muted" mb={4}>Execute read-only SQL queries against the database.</Text>
        <VStack align="stretch" gap={4}>
          <Textarea
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            placeholder="SELECT * FROM ... LIMIT 100;"
            rows={6}
            fontFamily="Roboto Mono, monospace"
            fontSize="sm"
            bg="code.bg"
          />
          <Flex gap={2}>
            <Button onClick={execute} loading={loading === 'query'}><FiPlay size={14} /> Execute</Button>
            <Button variant="outline" onClick={() => { setSql(''); setResult(null) }}><FiRefreshCw size={14} /> Clear</Button>
          </Flex>
          {result && (
            <Box as="pre" fontSize="xs" fontFamily="Roboto Mono, monospace" bg="code.bg" p={4} borderRadius="md" overflow="auto" maxH="500px">
              {JSON.stringify(result, null, 2)}
            </Box>
          )}
        </VStack>
      </Card.Body>
    </Card.Root>
  )
}
