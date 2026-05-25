import {
  Box,
  Flex,
  Text,
  Menu,
  Button,
  HStack,
  IconButton,
  Tooltip,
  Portal,
} from '@chakra-ui/react'
import { FiSun, FiMoon, FiChevronDown } from 'react-icons/fi'
import { useApp } from '../../stores/AppContext'
import { FACTION_KEYS, getFactionName } from '../../themes'
import type { FactionKey } from '../../themes/palettes'

export default function ThemeSwitcher() {
  const { state, dispatch } = useApp()

  const handleFactionChange = (key: FactionKey) => {
    dispatch({ type: 'SET_FACTION', payload: key })
  }

  const toggleColorMode = () => {
    dispatch({
      type: 'SET_COLOR_MODE',
      payload: state.colorMode === 'day' ? 'night' : 'day',
    })
  }

  return (
    <HStack gap={1}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <IconButton
            aria-label="Toggle color mode"
            variant="ghost"
            size="sm"
            onClick={toggleColorMode}
            color="fg.muted"
            w={8}
            h={8}
          >
            {state.colorMode === 'day' ? <FiSun size={16} /> : <FiMoon size={16} />}
          </IconButton>
        </Tooltip.Trigger>
        <Tooltip.Positioner>
          <Tooltip.Content bg="card.bg" border="1px solid" borderColor="border" borderRadius="md" px={3} py={1}>
            {state.colorMode === 'day' ? 'Switch to Night' : 'Switch to Day'}
          </Tooltip.Content>
        </Tooltip.Positioner>
      </Tooltip.Root>

      <Menu.Root>
        <Menu.Trigger asChild>
          <Button
            variant="outline"
            size="sm"
            borderColor="border"
            color="fg"
            _hover={{ borderColor: 'primary.DEFAULT', color: 'primary.DEFAULT' }}
            gap={2}
          >
            <Box
              w={2.5}
              h={2.5}
              borderRadius="full"
              bg="primary.DEFAULT"
            />
            <Text fontSize="xs">{getFactionName(state.faction)}</Text>
            <FiChevronDown size={12} />
          </Button>
        </Menu.Trigger>
        <Portal>
          <Menu.Positioner>
            <Menu.Content
              bg="card.bg"
              borderColor="border"
              borderRadius="lg"
              boxShadow="card"
              maxH="400px"
              overflowY="auto"
            >
              <Menu.ItemGroup title="Factions">
                {FACTION_KEYS.map((key) => (
                  <Menu.Item
                    key={key}
                    value={key}
                    onClick={() => handleFactionChange(key)}
                    bg={state.faction === key ? 'primary.subtle' : 'transparent'}
                    color={state.faction === key ? 'primary.DEFAULT' : 'fg'}
                    fontWeight={state.faction === key ? 'semibold' : 'normal'}
                    _hover={{ bg: 'bg.subtle' }}
                    cursor="pointer"
                    py={2}
                  >
                    <Flex align="center" gap={3}>
                      <Box
                        w={3}
                        h={3}
                        borderRadius="full"
                        bg="primary.DEFAULT"
                      />
                      <Text>{getFactionName(key)}</Text>
                    </Flex>
                  </Menu.Item>
                ))}
              </Menu.ItemGroup>
            </Menu.Content>
          </Menu.Positioner>
        </Portal>
      </Menu.Root>
    </HStack>
  )
}
