import { createToaster } from '@chakra-ui/react'

export const toaster = createToaster({
  placement: 'bottom-end',
  overlap: true,
})

export type ToasterRef = typeof toaster
