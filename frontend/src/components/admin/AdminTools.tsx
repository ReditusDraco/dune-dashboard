import { useState } from 'react'
import {
  Box, Flex, Heading, Text, Button, Input, Select, Textarea,
  SimpleGrid, Card, Tabs, Table, VStack, createListCollection,
} from '@chakra-ui/react'
import { FiAlertTriangle } from 'react-icons/fi'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

const SCOPE_OPTIONS = ['all', 'server', 'partition']
const SERVER_OPTIONS = ['na', 'eu', 'sea', 'sa', 'oc']
const PARTITION_OPTIONS = ['parrish', 'sietch', 'bazar']

const serverCollection = createListCollection({
  items: SERVER_OPTIONS.map((s) => ({ value: s, label: s.toUpperCase() })),
})

const partitionCollection = createListCollection({
  items: PARTITION_OPTIONS.map((p) => ({ value: p, label: p })),
})

const itemFieldCollection = createListCollection({
  items: [
    { value: 'stack_size', label: 'stack_size' },
    { value: 'quality_level', label: 'quality_level' },
    { value: 'durability', label: 'durability' },
    { value: 'ammo', label: 'ammo' },
  ],
})

const demoStateCollection = createListCollection({
  items: [
    { value: 'true', label: 'Demo' },
    { value: 'false', label: 'Normal' },
  ],
})

const limitCollection = createListCollection({
  items: [10, 25, 50, 100, 250].map((n) => ({ value: String(n), label: `${n} entries` })),
})

export default function AdminTools() {
  const [tab, setTab] = useState<'broadcast' | 'economy' | 'world' | 'character' | 'functions' | 'raw' | 'audit'>('broadcast')
  const { dispatch } = useApp()

  return (
    <Box>
      <Heading as="h1" fontFamily="Playfair Display, serif" fontSize="3xl" color="primary.DEFAULT" mb={6}>
        Admin Tools
      </Heading>

      <Tabs.Root value={tab} onValueChange={(e) => setTab(e.value as any)} mb={6}>
        <Tabs.List borderBottomWidth="1px" borderColor="border" overflowX="auto">
          {([
            { key: 'broadcast', label: 'Broadcast' },
            { key: 'economy', label: 'Economy' },
            { key: 'world', label: 'World' },
            { key: 'character', label: 'Character' },
            { key: 'functions', label: 'Functions' },
            { key: 'raw', label: 'Raw Query' },
            { key: 'audit', label: 'Audit Log' },
          ] as const).map((t) => (
            <Tabs.Trigger
              key={t.key}
              value={t.key}
              px={4}
              py={2.5}
              fontSize="sm"
              fontWeight="medium"
              whiteSpace="nowrap"
              _selected={{ color: 'primary.DEFAULT', borderColor: 'primary.DEFAULT' }}
              color="fg.muted"
              borderBottomWidth="2px"
              borderColor="transparent"
            >
              {t.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="broadcast" pt={4}>
          <BroadcastTab dispatch={dispatch} />
        </Tabs.Content>
        <Tabs.Content value="economy" pt={4}>
          <EconomyTab dispatch={dispatch} />
        </Tabs.Content>
        <Tabs.Content value="world" pt={4}>
          <WorldTab dispatch={dispatch} />
        </Tabs.Content>
        <Tabs.Content value="character" pt={4}>
          <CharacterTab dispatch={dispatch} />
        </Tabs.Content>
        <Tabs.Content value="functions" pt={4}>
          <FunctionsTab dispatch={dispatch} />
        </Tabs.Content>
        <Tabs.Content value="raw" pt={4}>
          <RawQueryTab dispatch={dispatch} />
        </Tabs.Content>
        <Tabs.Content value="audit" pt={4}>
          <AuditLogTab dispatch={dispatch} />
        </Tabs.Content>
      </Tabs.Root>
    </Box>
  )
}

function BroadcastTab({ dispatch }: { dispatch: any }) {
  const [message, setMessage] = useState('')
  const [scope, setScope] = useState('all')
  const [server, setServer] = useState('na')
  const [partition, setPartition] = useState('parrish')
  const [sending, setSending] = useState(false)

  const handleSend = async () => {
    if (!message.trim()) return
    setSending(true)
    try {
      const payload: any = { message: message.trim() }
      if (scope === 'server') payload.server = server
      if (scope === 'partition') {
        payload.server = server
        payload.partition = partition
      }
      const res = await client.post('/broadcast', payload)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Broadcast sent', type: 'success' } })
        setMessage('')
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    } finally {
      setSending(false)
    }
  }

  return (
    <Box maxW="xl">
      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={4} align="stretch">
            <Box>
              <Text fontSize="sm" color="fg.muted" mb={2}>Scope</Text>
              <Flex gap={2}>
                {SCOPE_OPTIONS.map((s) => (
                  <Button
                    key={s}
                    onClick={() => setScope(s)}
                    size="xs"
                    textTransform="capitalize"
                    variant={scope === s ? 'solid' : 'outline'}
                    bg={scope === s ? 'primary.subtle' : 'transparent'}
                    color={scope === s ? 'primary.DEFAULT' : 'fg.muted'}
                    borderColor={scope === s ? 'primary.DEFAULT' : 'border'}
                    borderRadius="md"
                    _hover={{ color: 'fg' }}
                  >
                    {s}
                  </Button>
                ))}
              </Flex>
            </Box>

            {scope !== 'all' && (
              <Box>
                <Text fontSize="sm" color="fg.muted" mb={2}>Server</Text>
                <Select.Root collection={serverCollection} value={[server]} onValueChange={(e) => setServer(e.value[0])}>
                  <Select.Trigger bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm">
                    <Select.ValueText />
                  </Select.Trigger>
                  <Select.Content>
                    {serverCollection.items.map((item) => (
                      <Select.Item item={item} key={item.value}>{item.label}</Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              </Box>
            )}

            {scope === 'partition' && (
              <Box>
                <Text fontSize="sm" color="fg.muted" mb={2}>Partition</Text>
                <Select.Root collection={partitionCollection} value={[partition]} onValueChange={(e) => setPartition(e.value[0])}>
                  <Select.Trigger bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm">
                    <Select.ValueText />
                  </Select.Trigger>
                  <Select.Content>
                    {partitionCollection.items.map((item) => (
                      <Select.Item item={item} key={item.value}>{item.label}</Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              </Box>
            )}

            <Box>
              <Text fontSize="sm" color="fg.muted" mb={2}>Message</Text>
              <Textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                bg="card.bg"
                borderColor="border"
                borderRadius="lg"
                fontSize="sm"
                resize="vertical"
                placeholder="Enter broadcast message..."
                _placeholder={{ color: 'fg.muted' }}
              />
            </Box>

            <Button
              onClick={handleSend}
              disabled={sending || !message.trim()}
              colorPalette="primary"
              borderRadius="lg"
              fontSize="sm"
              fontWeight="medium"
            >
              {sending ? 'Sending...' : 'Send Broadcast'}
            </Button>
          </VStack>
        </Card.Body>
      </Card.Root>
    </Box>
  )
}

function EconomyTab({ dispatch }: { dispatch: any }) {
  const [playerId, setPlayerId] = useState('')
  const [itemForm, setItemForm] = useState({ template_id: '', stack_size: '1', quality: '0', inventory_id: '' })
  const [editForm, setEditForm] = useState({ item_id: '', field: 'stack_size', value: '' })

  const post = async (endpoint: string, payload: any) => {
    try {
      const res = await client.post(endpoint, payload)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Success', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={3} align="stretch">
            <Text fontWeight="medium">Add Item</Text>
            <Input value={playerId} onChange={(e) => setPlayerId(e.target.value)} placeholder="Player ID" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Input value={itemForm.template_id} onChange={(e) => setItemForm({ ...itemForm, template_id: e.target.value })} placeholder="Template ID" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Input value={itemForm.stack_size} onChange={(e) => setItemForm({ ...itemForm, stack_size: e.target.value })} placeholder="Stack Size" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Input value={itemForm.quality} onChange={(e) => setItemForm({ ...itemForm, quality: e.target.value })} placeholder="Quality" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Input value={itemForm.inventory_id} onChange={(e) => setItemForm({ ...itemForm, inventory_id: e.target.value })} placeholder="Inventory ID" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Button
              onClick={() => post('/items/add', { player_id: parseInt(playerId), template_id: itemForm.template_id, stack_size: parseInt(itemForm.stack_size), quality_level: parseInt(itemForm.quality), inventory_id: parseInt(itemForm.inventory_id) || undefined })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="primary.DEFAULT"
              borderColor="primary.DEFAULT"
            >
              Add Item
            </Button>
          </VStack>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={3} align="stretch">
            <Text fontWeight="medium">Edit Item</Text>
            <Input value={editForm.item_id} onChange={(e) => setEditForm({ ...editForm, item_id: e.target.value })} placeholder="Item ID" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Select.Root collection={itemFieldCollection} value={[editForm.field]} onValueChange={(e) => setEditForm({ ...editForm, field: e.value[0] })}>
              <Select.Trigger bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm">
                <Select.ValueText />
              </Select.Trigger>
              <Select.Content>
                {itemFieldCollection.items.map((item) => (
                  <Select.Item item={item} key={item.value}>{item.label}</Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
            <Input value={editForm.value} onChange={(e) => setEditForm({ ...editForm, value: e.target.value })} placeholder="New value" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Flex gap={2}>
              <Button
                onClick={() => post(`/items/${editForm.item_id}`, { [editForm.field]: editForm.value })}
                size="xs"
                variant="outline"
                borderRadius="md"
                color="primary.DEFAULT"
                borderColor="primary.DEFAULT"
              >
                Update
              </Button>
              <Button
                onClick={() => post(`/items/${editForm.item_id}`, {})}
                size="xs"
                variant="outline"
                borderRadius="md"
                color="danger.DEFAULT"
                borderColor="danger.DEFAULT"
              >
                Delete
              </Button>
            </Flex>
          </VStack>
        </Card.Body>
      </Card.Root>
    </SimpleGrid>
  )
}

function WorldTab({ dispatch }: { dispatch: any }) {
  const [tpForm, setTpForm] = useState({ fls_id: '', partition: '', x: '', y: '', z: '' })

  const post = async (endpoint: string, payload: any) => {
    try {
      const res = await client.post(endpoint, payload)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Success', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={3} align="stretch">
            <Text fontWeight="medium">Teleport Player</Text>
            <Input value={tpForm.fls_id} onChange={(e) => setTpForm({ ...tpForm, fls_id: e.target.value })} placeholder="FLS ID / Account ID" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Input value={tpForm.partition} onChange={(e) => setTpForm({ ...tpForm, partition: e.target.value })} placeholder="Partition ID" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Flex gap={2}>
              <Input type="number" value={tpForm.x} onChange={(e) => setTpForm({ ...tpForm, x: e.target.value })} placeholder="X" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
              <Input type="number" value={tpForm.y} onChange={(e) => setTpForm({ ...tpForm, y: e.target.value })} placeholder="Y" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
              <Input type="number" value={tpForm.z} onChange={(e) => setTpForm({ ...tpForm, z: e.target.value })} placeholder="Z" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            </Flex>
            <Button
              onClick={() => post('/teleport', { fls_id: parseInt(tpForm.fls_id), partition_id: tpForm.partition, x: parseFloat(tpForm.x) || 0, y: parseFloat(tpForm.y) || 0, z: parseFloat(tpForm.z) || 0 })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="primary.DEFAULT"
              borderColor="primary.DEFAULT"
            >
              Teleport
            </Button>
          </VStack>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={3} align="stretch">
            <Text fontWeight="medium">Spice Control</Text>
            <Flex gap={2}>
              <Button
                onClick={() => post('/spice/reset', {})}
                size="xs"
                variant="outline"
                borderRadius="md"
                color="primary.DEFAULT"
                borderColor="primary.DEFAULT"
              >
                Reset Spice Fields
              </Button>
              <Button
                onClick={() => post('/spice/spawn', {})}
                size="xs"
                variant="outline"
                borderRadius="md"
                color="primary.DEFAULT"
                borderColor="primary.DEFAULT"
              >
                Force Spawn
              </Button>
            </Flex>
          </VStack>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={3} align="stretch">
            <Text fontWeight="medium">Partitions</Text>
            <Button
              onClick={() => client.get('/partitions').then((r) => dispatch({ type: 'ADD_TOAST', payload: { message: 'Partitions loaded', type: 'info' } }))}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="primary.DEFAULT"
              borderColor="primary.DEFAULT"
            >
              List Partitions
            </Button>
          </VStack>
        </Card.Body>
      </Card.Root>
    </SimpleGrid>
  )
}

function CharacterTab({ dispatch }: { dispatch: any }) {
  const [charId, setCharId] = useState('')
  const [newName, setNewName] = useState('')
  const [demoState, setDemoState] = useState('true')

  const post = async (endpoint: string, payload: any) => {
    try {
      const res = await client.post(endpoint, payload)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Success', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  return (
    <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={3} align="stretch">
            <Text fontWeight="medium">Rename Character</Text>
            <Input value={charId} onChange={(e) => setCharId(e.target.value)} placeholder="Account ID / Character ID" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New Name" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Button
              onClick={() => post(`/characters/${charId}/name`, { name: newName })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="primary.DEFAULT"
              borderColor="primary.DEFAULT"
            >
              Rename
            </Button>
          </VStack>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={3} align="stretch">
            <Text fontWeight="medium">Demo State</Text>
            <Input value={charId} onChange={(e) => setCharId(e.target.value)} placeholder="Account ID" bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm" />
            <Select.Root collection={demoStateCollection} value={[demoState]} onValueChange={(e) => setDemoState(e.value[0])}>
              <Select.Trigger bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm">
                <Select.ValueText />
              </Select.Trigger>
              <Select.Content>
                {demoStateCollection.items.map((item) => (
                  <Select.Item item={item} key={item.value}>{item.label}</Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
            <Button
              onClick={() => post(`/accounts/${charId}/demo`, { demo: demoState === 'true' })}
              size="xs"
              variant="outline"
              borderRadius="md"
              color="primary.DEFAULT"
              borderColor="primary.DEFAULT"
            >
              Set Demo State
            </Button>
          </VStack>
        </Card.Body>
      </Card.Root>

      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={3} align="stretch">
            <Text fontWeight="medium">Danger Zone</Text>
            <Flex wrap="wrap" gap={2}>
              <Button
                onClick={() => { if (confirm('Delete character?')) post(`/characters/${charId}`, {}) }}
                size="xs"
                variant="outline"
                borderRadius="md"
                color="danger.DEFAULT"
                borderColor="danger.DEFAULT"
              >
                Delete Character
              </Button>
              <Button
                onClick={() => { if (confirm('Delete account?')) post(`/accounts/${charId}`, {}) }}
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
        </Card.Body>
      </Card.Root>
    </SimpleGrid>
  )
}

function FunctionsTab({ dispatch }: { dispatch: any }) {
  const [schema, setSchema] = useState('')
  const [funcName, setFuncName] = useState('')
  const [args, setArgs] = useState('{}')
  const [result, setResult] = useState('')
  const [running, setRunning] = useState(false)

  const handleExecute = async () => {
    setRunning(true)
    try {
      const parsedArgs = JSON.parse(args || '{}')
      const res = await client.post('/functions/execute', { schema: schema || undefined, function: funcName, args: parsedArgs })
      if (res.data.success) {
        setResult(JSON.stringify(res.data.data, null, 2))
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Function executed', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.message, type: 'error' } })
    } finally {
      setRunning(false)
    }
  }

  return (
    <Box maxW="2xl">
      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={4} align="stretch">
            <SimpleGrid columns={2} gap={4}>
              <Box>
                <Text fontSize="sm" color="fg.muted" mb={2}>Schema (optional)</Text>
                <Input
                  value={schema}
                  onChange={(e) => setSchema(e.target.value)}
                  bg="card.bg"
                  borderColor="border"
                  borderRadius="lg"
                  fontSize="sm"
                  placeholder="e.g., public"
                />
              </Box>
              <Box>
                <Text fontSize="sm" color="fg.muted" mb={2}>Function Name</Text>
                <Input
                  value={funcName}
                  onChange={(e) => setFuncName(e.target.value)}
                  bg="card.bg"
                  borderColor="border"
                  borderRadius="lg"
                  fontSize="sm"
                  placeholder="e.g., get_player_stats"
                />
              </Box>
            </SimpleGrid>
            <Box>
              <Text fontSize="sm" color="fg.muted" mb={2}>Arguments (JSON)</Text>
              <Textarea
                value={args}
                onChange={(e) => setArgs(e.target.value)}
                rows={4}
                bg="card.bg"
                borderColor="border"
                borderRadius="lg"
                fontSize="sm"
                fontFamily="Roboto Mono, monospace"
                resize="vertical"
              />
            </Box>
            <Button
              onClick={handleExecute}
              disabled={running || !funcName}
              colorPalette="primary"
              borderRadius="lg"
              fontSize="sm"
              fontWeight="medium"
            >
              {running ? 'Running...' : 'Execute'}
            </Button>
            {result && (
              <Box
                as="pre"
                mt={4}
                fontSize="xs"
                fontFamily="Roboto Mono, monospace"
                bg="code.bg"
                p={4}
                borderRadius="md"
                overflow="auto"
                color="fg.muted"
              >
                {result}
              </Box>
            )}
          </VStack>
        </Card.Body>
      </Card.Root>
    </Box>
  )
}

function RawQueryTab({ dispatch }: { dispatch: any }) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState('')
  const [running, setRunning] = useState(false)

  const handleRun = async () => {
    setRunning(true)
    try {
      const res = await client.post('/query', { query })
      if (res.data.success) {
        setResult(JSON.stringify(res.data.data, null, 2))
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Query executed', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || e.message, type: 'error' } })
    } finally {
      setRunning(false)
    }
  }

  return (
    <Box maxW="3xl">
      <Card.Root borderRadius="lg" boxShadow="card" bg="card.bg">
        <Card.Body p={5}>
          <VStack gap={4} align="stretch">
            <Flex align="center" justify="space-between">
              <Text fontSize="sm" color="fg.muted">SQL Query (Read-Only SELECT)</Text>
              <Text fontSize="10px" color="danger.DEFAULT" textTransform="uppercase" letterSpacing="wider" bg="danger.subtle" px={2} py={0.5} borderRadius="md" borderWidth="1px" borderColor="danger.DEFAULT">
                <FiAlertTriangle style={{ display: 'inline', marginRight: 4 }} />
                Read Only
              </Text>
            </Flex>
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={6}
              bg="card.bg"
              borderColor="border"
              borderRadius="lg"
              fontSize="sm"
              fontFamily="Roboto Mono, monospace"
              resize="vertical"
              placeholder="SELECT * FROM public.characters LIMIT 10;"
              _placeholder={{ color: 'fg.muted' }}
            />
            <Button
              onClick={handleRun}
              disabled={running || !query.trim()}
              colorPalette="primary"
              borderRadius="lg"
              fontSize="sm"
              fontWeight="medium"
            >
              {running ? 'Running...' : 'Run Query'}
            </Button>
            {result && (
              <Box
                as="pre"
                mt={4}
                fontSize="xs"
                fontFamily="Roboto Mono, monospace"
                bg="code.bg"
                p={4}
                borderRadius="md"
                overflow="auto"
                color="fg.muted"
              >
                {result}
              </Box>
            )}
          </VStack>
        </Card.Body>
      </Card.Root>
    </Box>
  )
}

function AuditLogTab({ dispatch }: { dispatch: any }) {
  const [limit, setLimit] = useState(50)
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get(`/audit/logs?limit=${limit}`)
      if (res.data.success) setLogs(res.data.data)
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Flex align="center" gap={4} mb={4}>
        <Button
          onClick={load}
          disabled={loading}
          colorPalette="primary"
          borderRadius="lg"
          fontSize="sm"
          fontWeight="medium"
        >
          {loading ? 'Loading...' : 'Load Logs'}
        </Button>
        <Select.Root collection={limitCollection} value={[String(limit)]} onValueChange={(e) => setLimit(Number(e.value[0]))}>
          <Select.Trigger bg="card.bg" borderColor="border" borderRadius="md" fontSize="sm">
            <Select.ValueText />
          </Select.Trigger>
          <Select.Content>
            {limitCollection.items.map((item) => (
              <Select.Item item={item} key={item.value}>{item.label}</Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </Flex>
      <Box overflowX="auto" borderRadius="lg" borderWidth="1px" borderColor="border">
        <Table.Root variant="line" size="sm">
          <Table.Header>
            <Table.Row borderBottomWidth="1px" borderColor="border">
              <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" fontWeight="semibold" px={4} py={3}>Time</Table.ColumnHeader>
              <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" fontWeight="semibold" px={4} py={3}>Admin</Table.ColumnHeader>
              <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" fontWeight="semibold" px={4} py={3}>Action</Table.ColumnHeader>
              <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" fontWeight="semibold" px={4} py={3}>Target</Table.ColumnHeader>
              <Table.ColumnHeader textTransform="uppercase" fontSize="11px" color="fg.muted" fontWeight="semibold" px={4} py={3}>Details</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {logs.map((log, i) => (
              <Table.Row
                key={i}
                borderBottomWidth="1px"
                borderColor="border"
                _last={{ borderBottomWidth: 0 }}
                _hover={{ bg: 'bg.subtle' }}
              >
                <Table.Cell px={4} py={3} color="fg.muted" fontSize="xs">{new Date(log.timestamp).toLocaleString()}</Table.Cell>
                <Table.Cell px={4} py={3}>{log.admin_name}</Table.Cell>
                <Table.Cell px={4} py={3}>
                  <Text
                    as="span"
                    px={2}
                    py={0.5}
                    borderRadius="md"
                    fontSize="11px"
                    fontWeight="semibold"
                    bg="primary.subtle"
                    color="primary.DEFAULT"
                    borderWidth="1px"
                    borderColor="primary.DEFAULT"
                  >
                    {log.action}
                  </Text>
                </Table.Cell>
                <Table.Cell px={4} py={3}>{log.target_type}: {log.target_id}</Table.Cell>
                <Table.Cell px={4} py={3} fontSize="xs" color="fg.muted" maxW="md" truncate>{JSON.stringify(log.details)}</Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
      </Box>
    </Box>
  )
}
