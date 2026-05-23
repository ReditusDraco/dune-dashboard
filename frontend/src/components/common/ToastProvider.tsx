import { useEffect } from 'react'
import { useApp } from '../../stores/AppContext'

export default function ToastProvider() {
  const { state, dispatch } = useApp()

  useEffect(() => {
    if (state.toasts.length === 0) return
    const timers = state.toasts.map((t) =>
      setTimeout(() => {
        dispatch({ type: 'REMOVE_TOAST', payload: t.id })
      }, 4000)
    )
    return () => timers.forEach(clearTimeout)
  }, [state.toasts, dispatch])

  if (state.toasts.length === 0) return null

  return (
    <div className="fixed top-16 right-6 z-[100] flex flex-col gap-2">
      {state.toasts.map((t) => (
        <div
          key={t.id}
          className={`px-4 py-3 rounded-lg shadow-lg text-sm font-medium min-w-[240px] max-w-md border ${
            t.type === 'success'
              ? 'bg-success/10 border-success/30 text-success'
              : t.type === 'error'
              ? 'bg-danger/10 border-danger/30 text-danger'
              : t.type === 'warning'
              ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
              : 'bg-primary/10 border-primary/30 text-primary'
          }`}
        >
          {t.message}
        </div>
      ))}
    </div>
  )
}
