import { useState, useEffect } from 'react'
import {
  Box,
  Heading,
  Button,
  Flex,
  HStack,
  Table,
  Text,
  Spinner,
  Dialog,
  Portal,
  IconButton,
} from '@chakra-ui/react'
import { FiX, FiFolder, FiFile } from 'react-icons/fi'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

interface FileEntry {
  name: string
  path: string
  size: number
  is_dir: boolean
  mod_time: string
}

export default function FileBrowser() {
  const [path, setPath] = useState('/')
  const [files, setFiles] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [viewFile, setViewFile] = useState<{ path: string; content: string } | null>(null)
  const { dispatch } = useApp()

  const load = async (targetPath: string) => {
    setLoading(true)
    try {
      const res = await client.post('/files/list', { path: targetPath })
      if (res.data.success) {
        setFiles(res.data.data)
        setPath(targetPath)
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load('/')
  }, [])

  const view = async (filePath: string) => {
    try {
      const res = await client.get(`/files/view?path=${encodeURIComponent(filePath)}`)
      if (res.data.success) {
        setViewFile({ path: filePath, content: res.data.data })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  const breadcrumbs = path.split('/').filter(Boolean)

  return (
    <Box>
      <Heading as="h1" fontFamily="Playfair Display, serif" color="primary.DEFAULT" fontSize="2xl" mb={6}>
        File Browser
      </Heading>

      <HStack gap={1} mb={4} fontSize="sm">
        <Button
          variant="ghost"
          size="sm"
          color="primary.DEFAULT"
          fontWeight="normal"
          _hover={{ textDecoration: 'underline' }}
          onClick={() => load('/')}
        >
          /
        </Button>
        {breadcrumbs.map((crumb, i) => {
          const crumbPath = '/' + breadcrumbs.slice(0, i + 1).join('/')
          return (
            <HStack key={i} gap={1}>
              <Text color="fg.muted">/</Text>
              <Button
                variant="ghost"
                size="sm"
                color="primary.DEFAULT"
                fontWeight="normal"
                _hover={{ textDecoration: 'underline' }}
                onClick={() => load(crumbPath)}
              >
                {crumb}
              </Button>
            </HStack>
          )
        })}
      </HStack>

      <Box bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" overflow="hidden" boxShadow="card">
        <Table.ScrollArea>
          <Table.Root variant="line" size="sm">
            <Table.Header>
              <Table.Row bg="bg.subtle">
                <Table.ColumnHeader px={4} py={3} fontSize="2xs" fontWeight="semibold" color="fg.muted" textTransform="uppercase" letterSpacing="wider">
                  Name
                </Table.ColumnHeader>
                <Table.ColumnHeader px={4} py={3} fontSize="2xs" fontWeight="semibold" color="fg.muted" textTransform="uppercase" letterSpacing="wider">
                  Size
                </Table.ColumnHeader>
                <Table.ColumnHeader px={4} py={3} fontSize="2xs" fontWeight="semibold" color="fg.muted" textTransform="uppercase" letterSpacing="wider">
                  Modified
                </Table.ColumnHeader>
                <Table.ColumnHeader px={4} py={3} fontSize="2xs" fontWeight="semibold" color="fg.muted" textTransform="uppercase" letterSpacing="wider">
                  Actions
                </Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {path !== '/' && (
                <Table.Row
                  cursor="pointer"
                  _hover={{ bg: 'bg.subtle' }}
                  borderBottomWidth="1px"
                  borderColor="border"
                  transition="all 0.15s"
                  onClick={() => {
                    const parent = path.substring(0, path.lastIndexOf('/')) || '/'
                    load(parent)
                  }}
                >
                  <Table.Cell px={4} py={3} color="fg">
                    ..
                  </Table.Cell>
                  <Table.Cell px={4} py={3}>-</Table.Cell>
                  <Table.Cell px={4} py={3}>-</Table.Cell>
                  <Table.Cell px={4} py={3}>-</Table.Cell>
                </Table.Row>
              )}
              {loading ? (
                <Table.Row>
                  <Table.Cell colSpan={4} textAlign="center" py={8}>
                    <Flex align="center" justify="center" gap={2} color="fg.muted">
                      <Spinner size="sm" />
                      <Text fontSize="sm">Loading...</Text>
                    </Flex>
                  </Table.Cell>
                </Table.Row>
              ) : files.length === 0 ? (
                <Table.Row>
                  <Table.Cell colSpan={4} textAlign="center" py={8} color="fg.muted" fontSize="sm">
                    <Flex direction="column" align="center" gap={1}>
                      <FiFolder size={24} />
                      <Text>This directory is empty</Text>
                    </Flex>
                  </Table.Cell>
                </Table.Row>
              ) : (
                files.map((f, i) => (
                  <Table.Row
                    key={f.path}
                    cursor="pointer"
                    _hover={{ bg: 'bg.subtle' }}
                    borderBottomWidth="1px"
                    borderColor="border"
                    bg={i % 2 === 0 ? 'transparent' : 'bg.subtle'}
                    transition="all 0.15s"
                    onClick={() => f.is_dir && load(f.path)}
                  >
                    <Table.Cell px={4} py={3} color="fg">
                      <Flex align="center" gap={2}>
                        {f.is_dir ? <FiFolder size={16} /> : <FiFile size={16} />}
                        {f.name}
                      </Flex>
                    </Table.Cell>
                    <Table.Cell px={4} py={3} color="fg.muted">{f.is_dir ? '-' : formatBytes(f.size)}</Table.Cell>
                    <Table.Cell px={4} py={3} color="fg.muted">{new Date(f.mod_time).toLocaleString()}</Table.Cell>
                    <Table.Cell px={4} py={3}>
                      {!f.is_dir && (
                        <Button
                          variant="ghost"
                          size="xs"
                          color="primary.DEFAULT"
                          _hover={{ textDecoration: 'underline' }}
                          onClick={(e) => { e.stopPropagation(); view(f.path) }}
                        >
                          View
                        </Button>
                      )}
                    </Table.Cell>
                  </Table.Row>
                ))
              )}
            </Table.Body>
          </Table.Root>
        </Table.ScrollArea>
      </Box>

      <Dialog.Root open={!!viewFile} onOpenChange={(details) => { if (!details.open) setViewFile(null) }}>
        <Portal>
          <Dialog.Backdrop bg="black/60" backdropFilter="blur(4px)" />
          <Dialog.Positioner>
            <Dialog.Content
              bg="card.bg"
              borderWidth="1px"
              borderColor="border"
              borderRadius="xl"
              boxShadow="card"
              maxW="4xl"
              w="full"
              mx={4}
              maxH="80vh"
              display="flex"
              flexDirection="column"
            >
              <Dialog.Header
                display="flex"
                alignItems="center"
                justifyContent="space-between"
                borderBottomWidth="1px"
                borderColor="border"
                px={5}
                py={4}
              >
                <Dialog.Title
                  fontSize="lg"
                  fontFamily="Playfair Display, serif"
                  color="primary.DEFAULT"
                  truncate
                >
                  {viewFile?.path}
                </Dialog.Title>
                <Dialog.CloseTrigger asChild>
                  <IconButton
                    aria-label="Close"
                    variant="ghost"
                    size="sm"
                    onClick={() => setViewFile(null)}
                    color="fg.muted"
                    _hover={{ color: 'fg' }}
                  >
                    <FiX />
                  </IconButton>
                </Dialog.CloseTrigger>
              </Dialog.Header>
              <Dialog.Body p={5} overflow="auto" flex={1}>
                <Box
                  as="pre"
                  fontSize="xs"
                  fontFamily="Roboto Mono, monospace"
                  color="fg"
                  bg="code.bg"
                  p={4}
                  borderRadius="md"
                  overflow="auto"
                  whiteSpace="pre-wrap"
                >
                  {viewFile?.content}
                </Box>
              </Dialog.Body>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </Box>
  )
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
