import { useState, useEffect, useRef } from 'react'
import client from '../../api/client'

interface ChatMessage {
  id: string
  channel: string
  sender: string
  message: string
  timestamp: string
}

const CHANNELS = ['Global', 'Guild', 'System', 'Combat']

export default function ChatMonitor() {
  const [channel, setChannel] = useState('Global')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    async function load() {
      try {
        const res = await client.get(`/chat/history?channel=${channel}&limit=100`)
        if (res.data.success) {
          setMessages(res.data.data)
        }
      } catch (e) {
        console.error(e)
      }
    }
    load()
  }, [channel])

  useEffect(() => {
    const es = new EventSource('/api/events/stream')
    es.addEventListener('chat_message', (e) => {
      try {
        const msg: ChatMessage = JSON.parse(e.data)
        if (msg.channel === channel || channel === 'Global') {
          setMessages((prev) => [...prev.slice(-199), msg])
        }
      } catch {}
    })
    return () => es.close()
  }, [channel])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="h-[calc(100vh-140px)] flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-serif text-3xl text-primary">Chat Monitor</h1>
        <div className="flex gap-2">
          {CHANNELS.map((c) => (
            <button
              key={c}
              onClick={() => setChannel(c)}
              className={`px-3 py-1.5 rounded text-xs font-medium border ${
                channel === c
                  ? 'bg-primary/10 border-primary text-primary'
                  : 'bg-card-bg border-border text-text-muted hover:text-text-primary'
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 bg-card-bg border border-border rounded-lg overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-sm">
          {messages.map((msg) => (
            <div key={msg.id} className="flex gap-3">
              <span className="text-text-muted text-xs whitespace-nowrap">
                {new Date(msg.timestamp).toLocaleTimeString()}
              </span>
              <span className="text-primary font-semibold whitespace-nowrap">[{msg.channel}]</span>
              <span className="text-accent font-semibold whitespace-nowrap">{msg.sender}:</span>
              <span className="text-text-secondary break-all">{msg.message}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
