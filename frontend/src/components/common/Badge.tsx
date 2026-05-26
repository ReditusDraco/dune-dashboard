import { Badge as ChakraBadge } from '@chakra-ui/react'

interface BadgeProps {
  label: string
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
}

const variantMap: Record<string, { bg: string; color: string }> = {
  default: { bg: 'primary.subtle', color: 'primary.DEFAULT' },
  success: { bg: 'success.subtle', color: 'success.DEFAULT' },
  warning: { bg: 'warning.subtle', color: 'warning.DEFAULT' },
  danger: { bg: 'danger.subtle', color: 'danger.DEFAULT' },
  info: { bg: 'info.subtle', color: 'info.DEFAULT' },
}

export default function Badge({ label, variant = 'default' }: BadgeProps) {
  const colors = variantMap[variant] ?? variantMap.default

  return (
    <ChakraBadge
      variant="subtle"
      bg={colors.bg}
      color={colors.color}
      borderRadius="full"
      px={2.5}
      py={0.5}
      fontSize="xs"
      fontWeight="medium"
    >
      {label}
    </ChakraBadge>
  )
}
