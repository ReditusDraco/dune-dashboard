import { useState, useEffect } from 'react'
import {
  Box, Flex, Text, Heading, SimpleGrid,
  Card, Spinner, Progress, Separator, HStack, Circle, VStack
} from '@chakra-ui/react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts'
import { FiUsers, FiActivity, FiShield, FiServer, FiMap, FiDollarSign, FiFileText, FiDatabase, FiTerminal, FiRadio, FiMessageSquare } from 'react-icons/fi'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

interface Metrics {
  total_players: number
  online_players: number
  guild_count: number
  active_guilds: number
  server_count: number
  partition_count: number
  total_worth: number
  total_flavor_text: number
}

const STAT_CARDS = [
  { key: 'total_players', label: 'Total Players', icon: FiUsers, color: 'primary' },
  { key: 'online_players', label: 'Online', icon: FiActivity, color: 'success' },
  { key: 'guild_count', label: 'Guilds', icon: FiShield, color: 'info' },
  { key: 'active_guilds', label: 'Active Guilds', icon: FiShield, color: 'warning' },
  { key: 'server_count', label: 'Servers', icon: FiServer, color: 'primary' },
  { key: 'partition_count', label: 'Partitions', icon: FiMap, color: 'info' },
  { key: 'total_worth', label: 'Total Worth', icon: FiDollarSign, color: 'success' },
  { key: 'total_flavor_text', label: 'Flavor Text', icon: FiFileText, color: 'warning' },
] as const

function formatValue(key: string, value: number): string {
  if (key === 'total_worth') return '$' + Math.round(value).toLocaleString()
  return value.toLocaleString()
}

export default function Overview() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)
  const { state } = useApp()

  useEffect(() => {
    async function load() {
      try {
        const res = await client.get('/stats')
        if (res.data.success) {
          setMetrics(res.data.data)
        }
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()

    const es = new EventSource('/api/events/stream')
    es.addEventListener('metrics', (e) => {
      try {
        setMetrics(JSON.parse(e.data))
      } catch {}
    })
    return () => es.close()
  }, [])

  const onlineRatio = metrics
    ? [
      { name: 'Online', value: metrics.online_players, color: 'var(--chakra-colors-success-DEFAULT)' },
      { name: 'Offline', value: Math.max(0, metrics.total_players - metrics.online_players), color: 'var(--chakra-colors-border-DEFAULT)' },
    ]
    : []

  const guildRatio = metrics
    ? [
      { name: 'Active', value: metrics.active_guilds, color: 'var(--chakra-colors-warning-DEFAULT)' },
      { name: 'Inactive', value: Math.max(0, metrics.guild_count - metrics.active_guilds), color: 'var(--chakra-colors-border-DEFAULT)' },
    ]
    : []

  const healthItems = [
    { label: 'Database', key: 'database' as const, icon: FiDatabase },
    { label: 'SSH Tunnel', key: 'ssh' as const, icon: FiTerminal },
    { label: 'BG Director', key: 'bgd' as const, icon: FiRadio },
    { label: 'RMQ Game', key: 'rmq' as const, icon: FiMessageSquare },
  ]

  return (
    <Box>
      <Heading
        as="h1"
        fontSize="3xl"
        fontFamily="Playfair Display, serif"
        color="primary.DEFAULT"
        mb={6}
      >
        Dashboard Overview
      </Heading>

      {loading ? (
        <Flex align="center" justify="center" py={16}>
          <VStack gap={3}>
            <Spinner size="lg" color="primary.DEFAULT" />
            <Text color="fg.muted" fontSize="sm">Loading metrics...</Text>
          </VStack>
        </Flex>
      ) : (
        <>
          <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} gap={4}>
            {STAT_CARDS.map(({ key, label, icon: Icon, color }) => (
              <Card.Root
                key={key}
                bg="card.bg"
                borderWidth="1px"
                borderColor="border"
                borderRadius="xl"
                boxShadow="card"
                _hover={{ transform: 'translateY(-2px)', boxShadow: 'lg' }}
                transition="all 0.2s"
              >
                <Card.Body p={5}>
                  <Flex justify="space-between" align="start" mb={2}>
                    <Box
                      w={10}
                      h={10}
                      borderRadius="lg"
                      bg={`${color}.subtle`}
                      display="flex"
                      alignItems="center"
                      justifyContent="center"
                      color={`${color}.DEFAULT`}
                    >
                      <Icon size={20} />
                    </Box>
                  </Flex>
                  <Text
                    fontSize="2xl"
                    fontWeight="bold"
                    color="fg"
                    fontFamily="Roboto Mono, monospace"
                  >
                    {metrics ? formatValue(key, metrics[key as keyof Metrics]) : '-'}
                  </Text>
                  <Text fontSize="xs" color="fg.muted" mt={1}>
                    {label}
                  </Text>
                </Card.Body>
              </Card.Root>
            ))}
          </SimpleGrid>

          <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6} mt={8}>
            <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card">
              <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={4}>
                <Text fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" fontWeight="semibold">
                  Player Activity
                </Text>
              </Card.Header>
              <Card.Body p={5}>
                {metrics && onlineRatio.length > 0 ? (
                  <Flex align="center" gap={8}>
                    <Box w="160px" h="160px">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={onlineRatio}
                            cx="50%"
                            cy="50%"
                            innerRadius={45}
                            outerRadius={70}
                            paddingAngle={4}
                            dataKey="value"
                            stroke="none"
                          >
                            {onlineRatio.map((entry, i) => (
                              <Cell key={i} fill={entry.color} />
                            ))}
                          </Pie>
                          <RechartsTooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    </Box>
                    <VStack align="stretch" gap={4} flex={1}>
                      <Box>
                        <Flex justify="space-between" mb={1}>
                          <Text fontSize="sm" color="fg">Online</Text>
                          <Text fontSize="sm" fontWeight="semibold" color="success.DEFAULT">
                            {Math.round((metrics.online_players / Math.max(1, metrics.total_players)) * 100)}%
                          </Text>
                        </Flex>
                        <Progress.Root value={Math.round((metrics.online_players / Math.max(1, metrics.total_players)) * 100)} size="sm" borderRadius="full">
                          <Progress.Track bg="border">
                            <Progress.Range bg="success.DEFAULT" />
                          </Progress.Track>
                        </Progress.Root>
                      </Box>
                      <Box>
                        <Text fontSize="2xs" color="fg.muted" textTransform="uppercase" letterSpacing="wider">
                          {metrics.online_players.toLocaleString()} of {metrics.total_players.toLocaleString()} players online
                        </Text>
                      </Box>
                    </VStack>
                  </Flex>
                ) : (
                  <Text color="fg.muted" fontSize="sm" textAlign="center">No player data</Text>
                )}
              </Card.Body>
            </Card.Root>

            <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card">
              <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={4}>
                <Text fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" fontWeight="semibold">
                  System Health
                </Text>
              </Card.Header>
              <Card.Body p={5}>
                <VStack align="stretch" gap={4}>
                  {healthItems.map(({ label, icon: Icon }) => (
                    <Flex key={label} align="center" justify="space-between">
                      <Flex align="center" gap={3}>
                        <Box
                          w={8}
                          h={8}
                          borderRadius="md"
                          bg={`${state.connectionStatus[label.toLowerCase().replace(' ', '_') as keyof typeof state.connectionStatus] || state.connectionStatus.database ? 'success' : 'danger'}.subtle`}
                          display="flex"
                          alignItems="center"
                          justifyContent="center"
                        >
                          <Icon size={14} />
                        </Box>
                        <Text fontSize="sm" color="fg">{label}</Text>
                      </Flex>
                      <Flex align="center" gap={2}>
                        <Circle
                          size="8px"
                          bg={state.connectionStatus[label.toLowerCase().includes('database') ? 'database' : label.toLowerCase().includes('ssh') ? 'ssh' : label.toLowerCase().includes('bg') ? 'bgd' : 'rmq' as keyof typeof state.connectionStatus] ? 'success.DEFAULT' : 'danger.DEFAULT'}
                        />
                        <Text fontSize="xs" color="fg.muted">
                          {state.connectionStatus[label.toLowerCase().includes('database') ? 'database' : label.toLowerCase().includes('ssh') ? 'ssh' : label.toLowerCase().includes('bg') ? 'bgd' : 'rmq' as keyof typeof state.connectionStatus] ? 'Connected' : 'Disconnected'}
                        </Text>
                      </Flex>
                    </Flex>
                  ))}
                </VStack>
              </Card.Body>
            </Card.Root>
          </SimpleGrid>

          <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card" mt={6}>
            <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={4}>
              <Text fontFamily="Playfair Display, serif" fontSize="lg" color="primary.DEFAULT" fontWeight="semibold">
                Quick Actions
              </Text>
            </Card.Header>
            <Card.Body p={5}>
              <SimpleGrid columns={{ base: 2, md: 4 }} gap={3}>
                {['Broadcast Message', 'Player Search', 'Guild Lookup', 'Server Status'].map((label) => (
                  <Box
                    key={label}
                    as="button"
                    px={4}
                    py={3}
                    bg="primary.subtle"
                    borderWidth="1px"
                    borderColor="primary.subtle"
                    borderRadius="lg"
                    color="primary.DEFAULT"
                    fontSize="sm"
                    fontWeight="medium"
                    _hover={{ bg: 'primary.DEFAULT', color: 'white', borderColor: 'primary.DEFAULT' }}
                    transition="all 0.15s"
                    textAlign="left"
                    cursor="pointer"
                  >
                    {label}
                  </Box>
                ))}
              </SimpleGrid>
            </Card.Body>
          </Card.Root>
        </>
      )}
    </Box>
  )
}
