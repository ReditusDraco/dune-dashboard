import { ReactNode } from 'react'
import {
  Dialog,
  Portal,
  IconButton,
} from '@chakra-ui/react'
import { FiX } from 'react-icons/fi'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

export default function Modal({ open, onClose, title, children }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(e) => { if (!e.open) onClose() }}>
      <Portal>
        <Dialog.Backdrop bg="black/60" backdropFilter="blur(4px)" />
        <Dialog.Positioner>
          <Dialog.Content
            bg="card.bg"
            border="1px solid"
            borderColor="border"
            borderRadius="xl"
            boxShadow="card"
            maxW="600px"
            w="full"
            mx={4}
          >
            <Dialog.Header
              display="flex"
              alignItems="center"
              justifyContent="space-between"
              borderBottom="1px solid"
              borderColor="border"
              px={6}
              py={4}
            >
              <Dialog.Title
                fontSize="lg"
                fontWeight="semibold"
                fontFamily="Playfair Display, serif"
                color="primary.DEFAULT"
              >
                {title}
              </Dialog.Title>
              <Dialog.CloseTrigger asChild>
                <IconButton
                  aria-label="Close"
                  variant="ghost"
                  size="sm"
                  onClick={onClose}
                  color="fg.muted"
                  _hover={{ color: 'fg' }}
                >
                  <FiX />
                </IconButton>
              </Dialog.CloseTrigger>
            </Dialog.Header>
            <Dialog.Body px={6} py={4}>
              {children}
            </Dialog.Body>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  )
}
