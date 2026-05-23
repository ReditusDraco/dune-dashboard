interface BadgeProps {
  label: string
  variant?: 'default' | 'success' | 'warning' | 'danger'
}

export default function Badge({ label, variant = 'default' }: BadgeProps) {
  const classes: Record<string, string> = {
    default: 'bg-primary/10 text-primary border-primary/20',
    success: 'bg-success/10 text-success border-success/20',
    warning: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    danger: 'bg-danger/10 text-danger border-danger/20',
  }
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold border uppercase tracking-wide ${classes[variant]}`}
    >
      {label}
    </span>
  )
}
