import { useState, useEffect } from 'react'
import {
  Box,
  Heading,
  Button,
  Input,
  Flex,
  VStack,
  Card,
  Grid,
  Text,
  Spinner,
} from '@chakra-ui/react'
import { FiRefreshCw, FiSave, FiPlus } from 'react-icons/fi'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const { dispatch } = useApp()

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get('/settings')
      if (res.data.success) {
        setSettings(res.data.data)
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed to load settings', type: 'error' } })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await client.post('/settings', settings)
      if (res.data.success) {
        dispatch({ type: 'ADD_TOAST', payload: { message: 'Settings saved', type: 'success' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed to save', type: 'error' } })
    } finally {
      setSaving(false)
    }
  }

  const handleChange = (key: string, value: string) => {
    setSettings({ ...settings, [key]: value })
  }

  const addKey = () => {
    const key = prompt('Enter new setting key:')
    if (key) {
      setSettings({ ...settings, [key]: '' })
    }
  }

  return (
    <Box>
      <Heading as="h1" fontFamily="Playfair Display, serif" color="primary.DEFAULT" fontSize="2xl" mb={6}>
        Settings
      </Heading>

      <Flex gap={4} mb={6} wrap="wrap">
        <Button
          variant="solid"
          bg="primary.DEFAULT"
          color="white"
          size="sm"
          borderRadius="lg"
          onClick={load}
          disabled={loading}
          _hover={{ bg: 'primary.hover', transform: 'scale(1.02)' }}
          transition="all 0.15s"
        >
          <FiRefreshCw style={{ marginRight: 6 }} />
          {loading ? 'Loading...' : 'Reload'}
        </Button>
        <Button
          variant="solid"
          bg="success.DEFAULT"
          color="white"
          size="sm"
          borderRadius="lg"
          onClick={handleSave}
          disabled={saving}
          _hover={{ transform: 'scale(1.02)' }}
          transition="all 0.15s"
        >
          <FiSave style={{ marginRight: 6 }} />
          {saving ? 'Saving...' : 'Save Settings'}
        </Button>
        <Button
          variant="solid"
          bg="card.bg"
          color="fg"
          borderWidth="1px"
          borderColor="border"
          size="sm"
          borderRadius="lg"
          onClick={addKey}
          _hover={{ bg: 'bg.subtle', transform: 'scale(1.02)' }}
          transition="all 0.15s"
        >
          <FiPlus style={{ marginRight: 6 }} />
          Add Key
        </Button>
      </Flex>

      <Card.Root bg="card.bg" borderWidth="1px" borderColor="border" borderRadius="xl" boxShadow="card" maxW="3xl">
        <Card.Body p={5}>
          {loading ? (
            <Flex align="center" justify="center" py={8} gap={2} color="fg.muted">
              <Spinner size="sm" />
              <Text fontSize="sm">Loading settings...</Text>
            </Flex>
          ) : Object.entries(settings).length === 0 ? (
            <Flex direction="column" align="center" justify="center" py={8} color="fg.muted">
              <Text fontSize="sm">No settings found.</Text>
              <Text fontSize="xs" mt={1}>Click "Add Key" to create one.</Text>
            </Flex>
          ) : (
            <VStack gap={3} align="stretch">
              {Object.entries(settings).map(([key, value]) => (
                <Grid key={key} templateColumns="200px 1fr" gap={4} alignItems="center">
                  <Text as="label" fontSize="sm" color="fg.muted" truncate title={key}>
                    {key}
                  </Text>
                  <Input
                    value={value}
                    onChange={(e) => handleChange(key, e.target.value)}
                    bg="bg"
                    borderColor="border"
                    borderRadius="md"
                    px={3}
                    py={2}
                    fontSize="sm"
                    color="fg"
                  />
                </Grid>
              ))}
            </VStack>
          )}
        </Card.Body>
      </Card.Root>
    </Box>
  )
}
