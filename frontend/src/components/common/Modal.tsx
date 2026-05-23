interface ModalProps {
  open: boolean
  title: string
  onClose: () => void
  children: React.ReactNode
  maxWidth?: string
}

export default function Modal({ open, title, onClose, children, maxWidth = '500px' }: ModalProps) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className="bg-card-bg border border-border rounded-xl shadow-2xl w-full mx-4"
        style={{ maxWidth }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h3 className="font-serif text-lg text-text-primary">{title}</h3>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary text-xl leading-none"
          >
            &times;
          </button>
        </div>
        <div className="p-5 max-h-[80vh] overflow-auto">{children}</div>
      </div>
    </div>
  )
}
