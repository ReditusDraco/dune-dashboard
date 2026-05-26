import { Flex, Text, HStack, Box, Input, InputGroup } from '@chakra-ui/react'
import { FiSearch, FiUser } from 'react-icons/fi'
import { useApp } from '../../stores/AppContext'
import ConnectionBadge from './ConnectionBadge'
import ThemeSwitcher from './ThemeSwitcher'

export default function TopBar() {
  const { state } = useApp()

  return (
    <Flex
      as="header"
      h="56px"
      align="center"
      px={6}
      gap={4}
      bg="bg"
      borderBottom="1px solid"
      borderColor="border"
      position="sticky"
      top={0}
      zIndex={30}
    >
      <Box flex={1} maxW="400px">
        <InputGroup
          startElement={
            <Box pl={3} color="fg.muted">
              <FiSearch size={14} />
            </Box>
          }
          w="full"
        >
          <Input
            placeholder="Search players, guilds, accounts..."
            size="sm"
            borderRadius="lg"
            bg="bg.subtle"
            border="1px solid"
            borderColor="border"
            color="fg"
            _placeholder={{ color: 'fg.muted' }}
            _hover={{ borderColor: 'border' }}
            _focus={{ borderColor: 'primary.DEFAULT', boxShadow: `0 0 0 1px var(--chakra-colors-primary-DEFAULT)` }}
            fontSize="xs"
            pl={8}
          />
        </InputGroup>
      </Box>

      <HStack gap={3} ml="auto">
        <ConnectionBadge />
        <ThemeSwitcher />
        {state.user && (
          <Flex
            align="center"
            gap={2}
            px={3}
            py={1}
            borderRadius="full"
            bg="primary.subtle"
            border="1px solid"
            borderColor="primary.subtle"
          >
            <FiUser size={12} />
            <Text fontSize="xs" color="primary.DEFAULT" fontWeight="medium">
              {state.user}
            </Text>
          </Flex>
        )}
      </HStack>
    </Flex>
  )
}
