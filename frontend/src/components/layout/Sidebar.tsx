import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Box, Flex, VStack, Text, Collapsible, Separator } from '@chakra-ui/react'
import { FiHome, FiServer, FiUsers, FiShield, FiMap, FiTruck, FiBox, FiMessageSquare, FiTool, FiSliders, FiUserCheck, FiFolder, FiTerminal, FiSettings, FiZap } from 'react-icons/fi'

interface NavGroup {
  label: string
  icon: React.ElementType
  items: { path: string; label: string; icon: React.ElementType }[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Dashboard',
    icon: FiHome,
    items: [
      { path: '/', label: 'Overview', icon: FiHome },
      { path: '/server', label: 'Server', icon: FiServer },
    ],
  },
  {
    label: 'Players & World',
    icon: FiUsers,
    items: [
      { path: '/players', label: 'Players', icon: FiUsers },
      { path: '/guilds', label: 'Guilds', icon: FiShield },
      { path: '/map', label: 'Map', icon: FiMap },
      { path: '/vehicles', label: 'Vehicles', icon: FiTruck },
      { path: '/buildings', label: 'Buildings', icon: FiBox },
    ],
  },
  {
    label: 'Communication',
    icon: FiMessageSquare,
    items: [
      { path: '/chat', label: 'Chat Monitor', icon: FiMessageSquare },
    ],
  },
  {
    label: 'Administration',
    icon: FiTool,
    items: [
      { path: '/admin', label: 'Admin Tools', icon: FiTool },
      { path: '/director', label: 'Director', icon: FiSliders },
      { path: '/accounts', label: 'Accounts', icon: FiUserCheck },
    ],
  },
  {
    label: 'System',
    icon: FiFolder,
    items: [
      { path: '/files', label: 'Files', icon: FiFolder },
      { path: '/shell', label: 'Shell', icon: FiTerminal },
      { path: '/settings', label: 'Settings', icon: FiSettings },
    ],
  },
  {
    label: 'Experimental',
    icon: FiZap,
    items: [
      { path: '/experimental', label: 'Experimental', icon: FiZap },
    ],
  },
]

export default function Sidebar() {
  return (
    <Box
      as="aside"
      w="260px"
      minW="260px"
      h="100vh"
      position="fixed"
      left={0}
      top={0}
      bg="nav.bg"
      color="fg"
      overflowY="auto"
      borderRight="1px solid"
      borderColor="border"
      zIndex={40}
    >
      <Flex align="center" px={5} py={4} borderBottom="1px solid" borderColor="border">
        <Text
          fontFamily="Playfair Display, serif"
          fontSize="xl"
          fontWeight="bold"
          color="primary.DEFAULT"
          letterSpacing="wider"
        >
          Dune
        </Text>
        <Text
          fontSize="2xs"
          color="fg.muted"
          ml={2}
          mt={1}
          letterSpacing="widest"
          textTransform="uppercase"
        >
          Admin
        </Text>
      </Flex>

      <VStack gap={1} px={2} py={3} align="stretch">
        {NAV_GROUPS.map((group) => (
          <NavGroupSection key={group.label} group={group} />
        ))}
      </VStack>
    </Box>
  )
}

function NavGroupSection({ group }: { group: NavGroup }) {
  const location = useLocation()
  const groupActive = group.items.some(
    (item) =>
      location.pathname === item.path ||
      (item.path !== '/' && location.pathname.startsWith(item.path))
  )
  const [open, setOpen] = useState(groupActive)

  return (
    <Collapsible.Root open={open} onOpenChange={(e) => setOpen(e.open)}>
      <Collapsible.Trigger
        asChild
        cursor="pointer"
        display="flex"
        alignItems="center"
        gap={2}
        px={3}
        py={2}
        borderRadius="md"
        fontSize="xs"
        fontWeight="semibold"
        color="fg.muted"
        textTransform="uppercase"
        letterSpacing="wider"
        _hover={{ bg: 'bg.subtle', color: 'fg' }}
        transition="all 0.15s"
      >
        <Flex align="center" gap={2} w="full">
          <Box as="span" fontSize="sm">
            <group.icon />
          </Box>
          <Text flex={1}>{group.label}</Text>
          <Collapsible.Indicator
            transform={open ? 'rotate(180deg)' : 'rotate(0deg)'}
            transition="transform 0.15s"
          />
        </Flex>
      </Collapsible.Trigger>
      <Collapsible.Content>
        <VStack gap={0} align="stretch" pl={6} mt={1}>
          {group.items.map((item) => {
            const active =
              location.pathname === item.path ||
              (item.path !== '/' && location.pathname.startsWith(item.path))
            return (
              <Link key={item.path} to={item.path}>
                <Flex
                  align="center"
                  gap={2}
                  px={3}
                  py={2}
                  borderRadius="md"
                  fontSize="sm"
                  fontWeight={active ? 'semibold' : 'normal'}
                  color={active ? 'primary.DEFAULT' : 'fg.muted'}
                  bg={active ? 'primary.subtle' : 'transparent'}
                  borderLeft={active ? '3px solid' : '3px solid transparent'}
                  borderColor={active ? 'primary.DEFAULT' : 'transparent'}
                  _hover={
                    !active
                      ? { bg: 'bg.subtle', color: 'fg' }
                      : {}
                  }
                  transition="all 0.15s"
                >
                  <Box as="span" fontSize="xs" opacity={active ? 1 : 0.6}>
                    <item.icon />
                  </Box>
                  <Text>{item.label}</Text>
                </Flex>
              </Link>
            )
          })}
        </VStack>
      </Collapsible.Content>
    </Collapsible.Root>
  )
}
