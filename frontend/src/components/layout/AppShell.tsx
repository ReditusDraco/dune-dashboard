import { Box, Flex } from '@chakra-ui/react'
import { Toaster, ToastRoot, ToastTitle, ToastDescription } from '@chakra-ui/react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { toaster } from '../../toaster'

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <Flex minH="100vh" bg="bg">
      <Sidebar />
      <Box flex={1} ml="260px">
        <TopBar />
        <Box as="main" p={6} minH="calc(100vh - 56px)">
          {children}
        </Box>
      </Box>
      <Toaster toaster={toaster}>
        {(toast: any) => (
          <ToastRoot key={toast.id}>
            {toast.title && <ToastTitle>{toast.title}</ToastTitle>}
            {toast.description && <ToastDescription>{toast.description}</ToastDescription>}
          </ToastRoot>
        )}
      </Toaster>
    </Flex>
  )
}
