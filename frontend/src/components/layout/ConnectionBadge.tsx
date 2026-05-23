import { useApp } from '../../stores/AppContext'

export default function ConnectionBadge() {
  const { state } = useApp()
  const { database, ssh, bgd, rmq } = state.connectionStatus
  const allOk = database && ssh && bgd && rmq
  const someDown = !allOk && (database || ssh || bgd || rmq)

  return (
    <div className="flex items-center gap-2">
      <div
        className="w-2.5 h-2.5 rounded-full"
        style={{
          backgroundColor: allOk ? '#27ae60' : someDown ? '#f39c12' : '#c0392b',
          boxShadow: `0 0 6px ${allOk ? '#27ae60' : someDown ? '#f39c12' : '#c0392b'}`,
        }}
        title={`DB: ${database ? 'OK' : 'DOWN'} | SSH: ${ssh ? 'OK' : 'DOWN'} | BGD: ${bgd ? 'OK' : 'DOWN'} | RMQ: ${rmq ? 'OK' : 'DOWN'}`}
      />
    </div>
  )
}
