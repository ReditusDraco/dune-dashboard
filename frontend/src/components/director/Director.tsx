import { useState } from 'react'
import useSWR from 'swr'
import {
  Box,
  Heading,
  Tabs,
  Button,
  Input,
  Textarea,
  Field,
  Text,
  VStack,
  HStack,
  Spinner,
  Flex,
} from '@chakra-ui/react'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

export default function Director() {
  const [tab, setTab] = useState('battlegroup')
  const { dispatch } = useApp()

  const { data: bgData, isLoading: bgLoading } = useSWR('/director/battlegroup', fetcher, {
    refreshInterval: 15000,
  })

  const handlePost = async (endpoint: string, payload: any) => {
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
    <Box>
      <Heading as="h1" fontSize="3xl" fontFamily="Playfair Display, serif" color="primary.DEFAULT" mb={6}>
        Director Control
      </Heading>

      <Tabs.Root value={tab} onValueChange={(e) => setTab(e.value)} variant="line" mb={6}>
        <Tabs.List borderBottomWidth="1px" borderColor="border">
          <Tabs.Trigger value="battlegroup" fontWeight="medium">
            Battlegroup
          </Tabs.Trigger>
          <Tabs.Trigger value="config" fontWeight="medium">
            Config
          </Tabs.Trigger>
          <Tabs.Trigger value="transfer" fontWeight="medium">
            Transfer
          </Tabs.Trigger>
          <Tabs.Trigger value="fls" fontWeight="medium">
            FLS
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="battlegroup" pt={6}>
          <Box
            bg="card.bg"
            borderWidth="1px"
            borderColor="border"
            borderRadius="xl"
            boxShadow="card"
            p={5}
          >
            <Text fontSize="xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted" mb={4}>
              Battlegroup State
            </Text>
            {bgLoading ? (
              <Flex align="center" gap={2} color="fg.muted">
                <Spinner size="sm" />
                <Text fontSize="sm">Loading battlegroup data...</Text>
              </Flex>
            ) : bgData?.success ? (
              <Box
                as="pre"
                fontSize="xs"
                color="fg"
                fontFamily="Roboto Mono, monospace"
                bg="code.bg"
                p={4}
                borderRadius="lg"
                overflow="auto"
                maxH="60vh"
              >
                {JSON.stringify(bgData.data, null, 2)}
              </Box>
            ) : (
              <Text color="fg.muted">Loading battlegroup data...</Text>
            )}
          </Box>
        </Tabs.Content>

        <Tabs.Content value="config" pt={6}>
          <Box
            bg="card.bg"
            borderWidth="1px"
            borderColor="border"
            borderRadius="xl"
            boxShadow="card"
            p={5}
            maxW="xl"
          >
            <VStack gap={4} align="stretch">
              <Text fontSize="xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">
                Update Config
              </Text>

              <Field.Root>
                <Field.Label fontSize="sm" color="fg.muted">
                  Map Name
                </Field.Label>
                <Input
                  id="config-map"
                  bg="card.bg"
                  borderColor="border"
                  borderRadius="lg"
                  fontSize="sm"
                  placeholder="e.g., HaggaBasin"
                />
              </Field.Root>

              <Field.Root>
                <Field.Label fontSize="sm" color="fg.muted">
                  Config JSON
                </Field.Label>
                <Textarea
                  id="config-json"
                  rows={6}
                  bg="card.bg"
                  borderColor="border"
                  borderRadius="lg"
                  fontSize="sm"
                  fontFamily="Roboto Mono, monospace"
                  placeholder='{"maxPlayers": 100}'
                />
              </Field.Root>

              <HStack gap={2}>
                <Button
                  variant="solid"
                  size="sm"
                  bg="primary.DEFAULT"
                  borderRadius="lg"
                  _hover={{ bg: 'primary.hover' }}
                  transition="all 0.15s"
                  onClick={() => {
                    const map = (document.getElementById('config-map') as HTMLInputElement).value
                    const json = (document.getElementById('config-json') as HTMLTextAreaElement).value
                    handlePost('/director/config', { map, config: JSON.parse(json) })
                  }}
                >
                  Update Config
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  borderColor="danger.DEFAULT/30"
                  color="danger.DEFAULT"
                  bg="danger.subtle"
                  borderRadius="lg"
                  _hover={{ bg: 'danger.subtle/80' }}
                  transition="all 0.15s"
                  onClick={() => handlePost('/director/config/clear', {})}
                >
                  Clear Config
                </Button>
              </HStack>
            </VStack>
          </Box>
        </Tabs.Content>

        <Tabs.Content value="transfer" pt={6}>
          <Box
            bg="card.bg"
            borderWidth="1px"
            borderColor="border"
            borderRadius="xl"
            boxShadow="card"
            p={5}
            maxW="xl"
          >
            <VStack gap={4} align="stretch">
              <Text fontSize="xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">
                Transfer Rules
              </Text>
              <HStack gap={2}>
                <Button
                  variant="outline"
                  size="sm"
                  borderColor="danger.DEFAULT/30"
                  color="danger.DEFAULT"
                  bg="danger.subtle"
                  borderRadius="lg"
                  _hover={{ bg: 'danger.subtle/80' }}
                  transition="all 0.15s"
                  onClick={() => handlePost('/director/transfer/clear', {})}
                >
                  Clear Overrides
                </Button>
              </HStack>
            </VStack>
          </Box>
        </Tabs.Content>

        <Tabs.Content value="fls" pt={6}>
          <Box
            bg="card.bg"
            borderWidth="1px"
            borderColor="border"
            borderRadius="xl"
            boxShadow="card"
            p={5}
            maxW="xl"
          >
            <VStack gap={4} align="stretch">
              <Text fontSize="xs" textTransform="uppercase" letterSpacing="wider" color="fg.muted">
                FLS Settings
              </Text>
              <HStack gap={2}>
                <Button
                  variant="outline"
                  size="sm"
                  borderColor="danger.DEFAULT/30"
                  color="danger.DEFAULT"
                  bg="danger.subtle"
                  borderRadius="lg"
                  _hover={{ bg: 'danger.subtle/80' }}
                  transition="all 0.15s"
                  onClick={() => handlePost('/director/fls/clear', {})}
                >
                  Clear FLS Overrides
                </Button>
              </HStack>
            </VStack>
          </Box>
        </Tabs.Content>
      </Tabs.Root>
    </Box>
  )
}


