import { useState } from 'react'
import useSWR from 'swr'
import {
  Box, Flex, Text, Heading, Tabs, Card, Button,
  Table, Spinner, Badge as ChakraBadge, Separator, SimpleGrid
} from '@chakra-ui/react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts'
import { FiRefreshCw, FiPlus, FiMinus, FiServer, FiCpu, FiHardDrive, FiShield, FiRadio } from 'react-icons/fi'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'
import Badge from '../common/Badge'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

interface Pod {
  name: string
  namespace: string
  status: string
  restarts: number
  age: string
}

interface Deployment {
  name: string
  namespace: string
  replicas: number
  available: number
}

interface MetricPoint {
  timestamp: string
  cpu_percent: number
  memory_percent: number
}

const TAB_ICONS: Record<string, React.ElementType> = {
  pods: FiServer,
  deployments: FiRefreshCw,
  metrics: FiCpu,
  firewall: FiShield,
  rmq: FiRadio,
}

export default function ServerControl() {
  const [tab, setTab] = useState<'pods' | 'deployments' | 'metrics' | 'firewall' | 'rmq'>('pods')
  const { dispatch } = useApp()

  const { data: pods, mutate: mutatePods } = useSWR('/server/pods', fetcher, { refreshInterval: 15000 })
  const { data: deployments } = useSWR('/server/deployments', fetcher, { refreshInterval: 30000 })
  const { data: metrics } = useSWR('/server/metrics?hours=24', fetcher, { refreshInterval: 60000 })
  const { data: firewall } = useSWR('/server/firewall/status', fetcher, { refreshInterval: 30000 })
  const { data: rmq } = useSWR('/server/rmq/overview', fetcher, { refreshInterval: 30000 })

  const podList: Pod[] = pods?.success ? pods.data : []
  const deploymentList: Deployment[] = deployments?.success ? deployments.data : []
  const metricList: MetricPoint[] = metrics?.success ? metrics.data : []

  const handleRestart = async (deployment: string) => {
    try {
      const res = await client.post(`/server/deployments/${deployment}/restart`)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Restart initiated', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } }
      dispatch({ type: 'ADD_TOAST', payload: { message: err.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  const handleScale = async (deployment: string, replicas: number) => {
    try {
      const res = await client.post(`/server/deployments/${deployment}/scale`, { replicas })
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Scaled successfully', type: 'success' } })
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } } }
      dispatch({ type: 'ADD_TOAST', payload: { message: err.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  const chartData = metricList.map((m) => ({
    time: new Date(m.timestamp).toLocaleTimeString(),
    cpu: m.cpu_percent,
    memory: m.memory_percent,
  }))

  return (
    <Box>
      <Heading as="h1" fontSize="3xl" fontFamily="Playfair Display, serif" color="primary.DEFAULT" mb={6}>
        Server Control
      </Heading>

      <Tabs.Root
        value={tab}
        onValueChange={(e) => setTab(e.value as typeof tab)}
        variant="line"
        mb={6}
      >
        <Tabs.List borderBottomWidth="1px" borderColor="border" gap={0}>
          {(['pods', 'deployments', 'metrics', 'firewall', 'rmq'] as const).map((t) => {
            const Icon = TAB_ICONS[t]
            return (
              <Tabs.Trigger
                key={t}
                value={t}
                px={4}
                py={2.5}
                fontSize="sm"
                fontWeight="medium"
                textTransform="capitalize"
                color="fg.muted"
                borderBottom="2px solid transparent"
                _selected={{
                  color: 'primary.DEFAULT',
                  borderColor: 'primary.DEFAULT',
                }}
                transition="all 0.15s"
                gap={2}
              >
                <Icon size={14} />
                {t}
              </Tabs.Trigger>
            )
          })}
        </Tabs.List>

        <Tabs.Content value="pods" pt={4}>
          <Table.ScrollArea borderWidth="1px" borderColor="border" borderRadius="lg">
            <Table.Root variant="line" size="sm" stickyHeader>
              <Table.Header>
                <Table.Row bg="bg.subtle">
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Name</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Namespace</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Status</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Restarts</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Age</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Actions</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {podList.map((pod) => (
                  <Table.Row key={pod.name} _hover={{ bg: 'bg.subtle' }}>
                    <Table.Cell fontFamily="Roboto Mono, monospace" fontSize="xs">{pod.name}</Table.Cell>
                    <Table.Cell fontSize="sm">{pod.namespace}</Table.Cell>
                    <Table.Cell>
                      <Badge
                        label={pod.status}
                        variant={pod.status === 'Running' ? 'success' : pod.status === 'Pending' ? 'warning' : 'danger'}
                      />
                    </Table.Cell>
                    <Table.Cell fontSize="sm">{pod.restarts}</Table.Cell>
                    <Table.Cell fontSize="sm">{pod.age}</Table.Cell>
                    <Table.Cell>
                      <Button variant="ghost" size="xs" color="primary.DEFAULT" onClick={() => handleRestart(pod.name)}>
                        Restart
                      </Button>
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
          </Table.ScrollArea>
        </Tabs.Content>

        <Tabs.Content value="deployments" pt={4}>
          <Table.ScrollArea borderWidth="1px" borderColor="border" borderRadius="lg">
            <Table.Root variant="line" size="sm" stickyHeader>
              <Table.Header>
                <Table.Row bg="bg.subtle">
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Name</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Namespace</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Replicas</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Available</Table.ColumnHeader>
                  <Table.ColumnHeader fontSize="2xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">Actions</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {deploymentList.map((dep) => (
                  <Table.Row key={dep.name} _hover={{ bg: 'bg.subtle' }}>
                    <Table.Cell fontFamily="Roboto Mono, monospace" fontSize="xs">{dep.name}</Table.Cell>
                    <Table.Cell fontSize="sm">{dep.namespace}</Table.Cell>
                    <Table.Cell fontSize="sm">{dep.replicas}</Table.Cell>
                    <Table.Cell fontSize="sm">{dep.available}</Table.Cell>
                    <Table.Cell>
                      <Flex gap={1}>
                        <Button variant="outline" size="xs" borderColor="primary.DEFAULT" color="primary.DEFAULT" onClick={() => handleScale(dep.name, dep.replicas + 1)}>
                          <FiPlus size={12} />
                        </Button>
                        <Button variant="outline" size="xs" borderColor="border" color="fg.muted" onClick={() => handleScale(dep.name, Math.max(0, dep.replicas - 1))}>
                          <FiMinus size={12} />
                        </Button>
                        <Button variant="outline" size="xs" borderColor="danger.DEFAULT" color="danger.DEFAULT" onClick={() => handleRestart(dep.name)}>
                          Restart
                        </Button>
                      </Flex>
                    </Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
          </Table.ScrollArea>
        </Tabs.Content>

        <Tabs.Content value="metrics" pt={4}>
          {metricList.length === 0 ? (
            <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl">
              <Card.Body p={8} textAlign="center">
                <Flex direction="column" align="center" gap={3}>
                  <FiCpu size={40} style={{ opacity: 0.3 }} />
                  <Text color="fg.muted">No metrics available</Text>
                </Flex>
              </Card.Body>
            </Card.Root>
          ) : (
            <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6}>
              <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card">
                <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={4}>
                  <Flex align="center" gap={2}>
                    <Box w={3} h={3} borderRadius="full" bg="primary.DEFAULT" />
                    <Text fontFamily="Playfair Display, serif" fontSize="md" color="primary.DEFAULT" fontWeight="semibold">
                      CPU Usage (24h)
                    </Text>
                  </Flex>
                </Card.Header>
                <Card.Body p={4}>
                  <Box w="full" h="280px">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData}>
                        <defs>
                          <linearGradient id="cpuGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--chakra-colors-primary-DEFAULT)" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="var(--chakra-colors-primary-DEFAULT)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chakra-colors-border-DEFAULT)" />
                        <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'var(--chakra-colors-fg-muted)' }} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 10, fill: 'var(--chakra-colors-fg-muted)' }} unit="%" />
                        <Tooltip contentStyle={{ background: 'var(--chakra-colors-card-bg)', border: '1px solid var(--chakra-colors-border-DEFAULT)', borderRadius: '8px', fontSize: '12px' }} />
                        <Area type="monotone" dataKey="cpu" stroke="var(--chakra-colors-primary-DEFAULT)" fill="url(#cpuGrad)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </Box>
                </Card.Body>
              </Card.Root>

              <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card">
                <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={4}>
                  <Flex align="center" gap={2}>
                    <Box w={3} h={3} borderRadius="full" bg="success.DEFAULT" />
                    <Text fontFamily="Playfair Display, serif" fontSize="md" color="primary.DEFAULT" fontWeight="semibold">
                      Memory Usage (24h)
                    </Text>
                  </Flex>
                </Card.Header>
                <Card.Body p={4}>
                  <Box w="full" h="280px">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData}>
                        <defs>
                          <linearGradient id="memGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--chakra-colors-success-DEFAULT)" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="var(--chakra-colors-success-DEFAULT)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--chakra-colors-border-DEFAULT)" />
                        <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'var(--chakra-colors-fg-muted)' }} interval="preserveStartEnd" />
                        <YAxis tick={{ fontSize: 10, fill: 'var(--chakra-colors-fg-muted)' }} unit="%" />
                        <Tooltip contentStyle={{ background: 'var(--chakra-colors-card-bg)', border: '1px solid var(--chakra-colors-border-DEFAULT)', borderRadius: '8px', fontSize: '12px' }} />
                        <Area type="monotone" dataKey="memory" stroke="var(--chakra-colors-success-DEFAULT)" fill="url(#memGrad)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </Box>
                </Card.Body>
              </Card.Root>
            </SimpleGrid>
          )}
        </Tabs.Content>

        <Tabs.Content value="firewall" pt={4}>
          <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card">
            <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={4}>
              <Flex align="center" gap={2}>
                <FiShield size={16} color="currentColor" />
                <Text fontFamily="Playfair Display, serif" fontSize="md" color="primary.DEFAULT" fontWeight="semibold">
                  Firewall Status
                </Text>
              </Flex>
            </Card.Header>
            <Card.Body p={5}>
              {firewall?.success ? (
                <Box as="pre" fontSize="xs" color="fg" fontFamily="Roboto Mono, monospace" bg="code.bg" p={4} borderRadius="lg" overflow="auto">
                  {JSON.stringify(firewall.data, null, 2)}
                </Box>
              ) : (
                <Text color="fg.muted" fontSize="sm">No firewall data available</Text>
              )}
            </Card.Body>
          </Card.Root>
        </Tabs.Content>

        <Tabs.Content value="rmq" pt={4}>
          <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card">
            <Card.Header borderBottomWidth="1px" borderColor="border" px={5} py={4}>
              <Flex align="center" gap={2}>
                <FiRadio size={16} color="currentColor" />
                <Text fontFamily="Playfair Display, serif" fontSize="md" color="primary.DEFAULT" fontWeight="semibold">
                  RMQ Overview
                </Text>
              </Flex>
            </Card.Header>
            <Card.Body p={5}>
              {rmq?.success ? (
                <Box as="pre" fontSize="xs" color="fg" fontFamily="Roboto Mono, monospace" bg="code.bg" p={4} borderRadius="lg" overflow="auto">
                  {JSON.stringify(rmq.data, null, 2)}
                </Box>
              ) : (
                <Text color="fg.muted" fontSize="sm">No RMQ data available</Text>
              )}
            </Card.Body>
          </Card.Root>
        </Tabs.Content>
      </Tabs.Root>
    </Box>
  )
}
