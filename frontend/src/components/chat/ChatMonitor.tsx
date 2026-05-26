import { useState, useEffect, useRef } from 'react'
import {
  Box,
  Heading,
  HStack,
  Flex,
  Button,
  Text,
  VStack,
} from '@chakra-ui/react'
import { FiMessageSquare } from 'react-icons/fi'
import client from '../../api/client'

interface ChatMessage {
  id: string
  channel: string
  sender: string
  message: string
  timestamp: string
}

const CHANNELS = ['Global', 'Guild', 'System', 'Combat']

export default function ChatMonitor() {
  const [channel, setChannel] = useState('Global')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    async function load() {
      try {
        const res = await client.get(`/chat/history?channel=${channel}&limit=100`)
        if (res.data.success) {
          setMessages(res.data.data)
        }
      } catch (e) {
        console.error(e)
      }
    }
    load()
  }, [channel])

  useEffect(() => {
    const es = new EventSource('/api/events/stream')
    es.addEventListener('chat_message', (e) => {
      try {
        const msg: ChatMessage = JSON.parse(e.data)
        if (msg.channel === channel || channel === 'Global') {
          setMessages((prev) => [...prev.slice(-199), msg])
        }
      } catch {}
    })
    return () => es.close()
  }, [channel])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <Flex direction="column" h="calc(100vh - 140px)">
      <Flex align="center" justify="space-between" mb={4}>
        <Heading as="h1" fontSize="3xl" fontFamily="Playfair Display, serif" color="primary.DEFAULT">
          Chat Monitor
        </Heading>
        <HStack gap={2}>
          {CHANNELS.map((c) => (
            <Button
              key={c}
              onClick={() => setChannel(c)}
              size="xs"
              borderRadius="md"
              fontWeight="medium"
              borderWidth="1px"
              borderColor={channel === c ? 'primary.DEFAULT' : 'border'}
              bg={channel === c ? 'primary.subtle' : 'card.bg'}
              color={channel === c ? 'primary.DEFAULT' : 'fg.muted'}
              _hover={channel === c ? {} : { color: 'fg' }}
              transition="all 0.15s"
            >
              {c}
            </Button>
          ))}
        </HStack>
      </Flex>

      <Box
        flex={1}
        bg="card.bg"
        borderWidth="1px"
        borderColor="border"
        borderRadius="xl"
        overflow="hidden"
        display="flex"
        flexDirection="column"
      >
        <Box
          flex={1}
          overflowY="auto"
          p={4}
          fontFamily="Roboto Mono, monospace"
        >
          {messages.length === 0 ? (
            <Flex align="center" justify="center" h="full" color="fg.muted">
              <VStack gap={3}>
                <FiMessageSquare size={40} />
                <Text fontSize="sm">Waiting for messages...</Text>
              </VStack>
            </Flex>
          ) : (
            <VStack gap={2} align="stretch">
              {messages.map((msg) => (
                <HStack key={msg.id} gap={3} align="baseline">
                  <Text color="fg.muted" fontSize="xs" whiteSpace="nowrap" flexShrink={0}>
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </Text>
                  <Text color="primary.DEFAULT" fontWeight="semibold" whiteSpace="nowrap" flexShrink={0}>
                    [{msg.channel}]
                  </Text>
                  <Text color="warning.DEFAULT" fontWeight="semibold" whiteSpace="nowrap" flexShrink={0}>
                    {msg.sender}:
                  </Text>
                  <Text color="fg" wordBreak="break-all">
                    {msg.message}
                  </Text>
                </HStack>
              ))}
            </VStack>
          )}
          <Box ref={bottomRef} />
        </Box>
      </Box>
    </Flex>
  )
}
