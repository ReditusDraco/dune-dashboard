import { Box, Flex, Text, Tooltip, VStack, Circle } from '@chakra-ui/react'
import { FiWifi, FiWifiOff } from 'react-icons/fi'
import { useApp } from '../../stores/AppContext'

const SERVICES = [
  { key: 'database' as const, label: 'Database' },
  { key: 'ssh' as const, label: 'SSH Tunnel' },
  { key: 'bgd' as const, label: 'BG Director' },
  { key: 'rmq' as const, label: 'RMQ' },
]

export default function ConnectionBadge() {
  const { state } = useApp()
  const statuses = SERVICES.map((s) => state.connectionStatus[s.key])
  const upCount = statuses.filter(Boolean).length
  const allUp = upCount === statuses.length
  const allDown = upCount === 0

  const dotColor = allUp ? 'success.DEFAULT' : allDown ? 'danger.DEFAULT' : 'warning.DEFAULT'

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <Flex
          align="center"
          gap={1.5}
          px={2.5}
          py={1}
          borderRadius="full"
          bg="bg.subtle"
          border="1px solid"
          borderColor="border.subtle"
          cursor="default"
        >
          {allUp ? (
            <FiWifi size={14} color="currentColor" />
          ) : (
            <FiWifiOff size={14} color="currentColor" />
          )}
          <Circle size="6px" bg={dotColor} />
        </Flex>
      </Tooltip.Trigger>
      <Tooltip.Positioner>
        <Tooltip.Content bg="card.bg" border="1px solid" borderColor="border" borderRadius="md" p={3}>
          <VStack align="stretch" gap={2} minW="160px">
            <Text fontSize="xs" fontWeight="semibold" color="fg" mb={1}>
              Service Status
            </Text>
            {SERVICES.map((s) => (
              <Flex key={s.key} justify="space-between" align="center" gap={4}>
                <Text fontSize="xs" color="fg.muted">
                  {s.label}
                </Text>
                <Flex align="center" gap={1.5}>
                  <Circle
                    size="6px"
                    bg={state.connectionStatus[s.key] ? 'success.DEFAULT' : 'danger.DEFAULT'}
                  />
                  <Text fontSize="2xs" color="fg.muted">
                    {state.connectionStatus[s.key] ? 'OK' : 'DOWN'}
                  </Text>
                </Flex>
              </Flex>
            ))}
          </VStack>
        </Tooltip.Content>
      </Tooltip.Positioner>
    </Tooltip.Root>
  )
}
