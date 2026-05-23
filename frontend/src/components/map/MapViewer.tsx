import { useState, useEffect, useRef } from 'react'
import useSWR from 'swr'
import client from '../../api/client'

const fetcher = (url: string) => client.get(url).then((r) => r.data)

interface MapMarker {
  id: string
  name: string
  x: number
  y: number
  type: 'player' | 'vehicle' | 'building' | 'landclaim'
}

export default function MapViewer() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [markers, setMarkers] = useState<MapMarker[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [selected, setSelected] = useState<MapMarker | null>(null)
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef({ x: 0, y: 0 })

  const { data: mapData } = useSWR('/partitions', fetcher, { refreshInterval: 60000 })

  useEffect(() => {
    const allMarkers: MapMarker[] = []
    if (mapData?.success) {
      (mapData.data || []).forEach((p: any) => {
        if (p.center_x != null && p.center_y != null) {
          allMarkers.push({
            id: `partition-${p.partition_id}`,
            name: p.name || `Partition ${p.partition_id}`,
            x: p.center_x,
            y: p.center_y,
            type: 'building',
          })
        }
      })
    }
    setMarkers(allMarkers)
  }, [mapData])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    ctx.fillStyle = '#1a1a1a'
    ctx.fillRect(0, 0, rect.width, rect.height)

    ctx.strokeStyle = '#333'
    ctx.lineWidth = 1
    const gridSize = 50 * scale
    for (let x = offset.x % gridSize; x < rect.width; x += gridSize) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, rect.height)
      ctx.stroke()
    }
    for (let y = offset.y % gridSize; y < rect.height; y += gridSize) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(rect.width, y)
      ctx.stroke()
    }

    const filtered = filter === 'all' ? markers : markers.filter((m) => m.type === filter)

    filtered.forEach((m) => {
      const sx = rect.width / 2 + (m.x * 0.001 * scale) + offset.x
      const sy = rect.height / 2 + (m.y * 0.001 * scale) + offset.y

      ctx.beginPath()
      ctx.arc(sx, sy, 6, 0, Math.PI * 2)
      ctx.fillStyle = m.type === 'player' ? '#27ae60' : m.type === 'vehicle' ? '#4a90d9' : '#d4af37'
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 1
      ctx.stroke()

      ctx.fillStyle = '#c0c0c0'
      ctx.font = '10px Inter'
      ctx.fillText(m.name, sx + 10, sy + 3)
    })
  }, [markers, filter, scale, offset])

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const newScale = Math.max(0.1, Math.min(10, scale + (e.deltaY > 0 ? -0.1 : 0.1)))
    setScale(newScale)
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true)
    dragStart.current = { x: e.clientX - offset.x, y: e.clientY - offset.y }
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return
    setOffset({ x: e.clientX - dragStart.current.x, y: e.clientY - dragStart.current.y })
  }

  const handleMouseUp = () => setIsDragging(false)

  return (
    <div className="h-[calc(100vh-140px)] flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-serif text-3xl text-primary">Map Viewer</h1>
        <div className="flex gap-2">
          {(['all', 'player', 'vehicle', 'building'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded text-xs font-medium border capitalize ${
                filter === f
                  ? 'bg-primary/10 border-primary text-primary'
                  : 'bg-card-bg border-border text-text-muted hover:text-text-primary'
              }`}
            >
              {f}
            </button>
          ))}
          <button
            onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }) }}
            className="px-3 py-1.5 rounded text-xs font-medium border bg-card-bg border-border text-text-muted hover:text-text-primary"
          >
            Reset View
          </button>
        </div>
      </div>

      <div className="flex-1 bg-card-bg border border-border rounded-lg overflow-hidden relative">
        <canvas
          ref={canvasRef}
          className="w-full h-full cursor-grab active:cursor-grabbing"
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        />
        <div className="absolute bottom-4 left-4 bg-card-bg/90 border border-border rounded px-3 py-2 text-xs text-text-muted">
          Zoom: {scale.toFixed(1)}x | Markers: {markers.length}
        </div>
      </div>
    </div>
  )
}
