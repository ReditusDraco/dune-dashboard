import { useEffect, useRef } from 'react'
import { useApp } from '../stores/AppContext'

export function useRealtime() {
  const { dispatch } = useApp()
  const evtSource = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/events/stream')
    evtSource.current = es

    es.onopen = () => {
      console.log('[SSE] Connected')
    }

    es.addEventListener('battlegroup_update', (e) => {
      try {
        const data = JSON.parse(e.data)
        console.log('[SSE] battlegroup_update', data)
      } catch {}
    })

    es.addEventListener('rmq_health', (e) => {
      try {
        const data = JSON.parse(e.data)
        console.log('[SSE] rmq_health', data)
      } catch {}
    })

    es.addEventListener('connection_status', (e) => {
      try {
        const data = JSON.parse(e.data)
        dispatch({ type: 'SET_CONNECTION', payload: data })
      } catch {}
    })

    es.addEventListener('chat_message', (e) => {
      try {
        const data = JSON.parse(e.data)
        console.log('[SSE] chat_message', data)
      } catch {}
    })

    es.onerror = () => {
      console.warn('[SSE] Connection error')
    }

    return () => {
      es.close()
    }
  }, [dispatch])
}
