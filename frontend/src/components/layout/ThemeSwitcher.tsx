import { useState, useRef, useEffect } from 'react'
import { useApp } from '../../stores/AppContext'

const THEMES = [
  { key: 'default', label: 'Classic Dune' },
  { key: 'atreides', label: 'House Atreides' },
  { key: 'harkonnen', label: 'House Harkonnen' },
  { key: 'fremen', label: 'Fremen' },
  { key: 'bene-gesserit', label: 'Bene Gesserit' },
  { key: 'spacing-guild', label: 'Spacing Guild' },
  { key: 'emperor', label: 'Emperor' },
  { key: 'corrino', label: 'House Corrino' },
  { key: 'mentat', label: 'Mentat' },
  { key: 'sardaukar', label: 'Sardaukar' },
  { key: 'tleilax', label: 'Bene Tleilax' },
  { key: 'ordos', label: 'House Ordos' },
  { key: 'ix', label: 'Ix' },
  { key: 'choam', label: 'CHOAM' },
]

export default function ThemeSwitcher() {
  const { state, dispatch } = useApp()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="w-6 h-6 rounded-full"
        style={{ background: 'linear-gradient(135deg, var(--primary) 50%, var(--bg) 50%)' }}
        title="Change theme"
      />
      {open && (
        <div className="absolute right-0 mt-2 w-56 bg-card-bg border border-border rounded-lg shadow-xl z-50 py-2">
          {THEMES.map((t) => (
            <button
              key={t.key}
              onClick={() => {
                dispatch({ type: 'SET_THEME', payload: t.key })
                setOpen(false)
              }}
              className={`w-full text-left px-4 py-2 text-sm flex items-center gap-3 hover:bg-hover transition-colors ${
                state.theme === t.key ? 'text-primary font-semibold' : 'text-text-secondary'
              }`}
            >
              <span
                className="w-4 h-4 rounded border border-border"
                style={{ background: `linear-gradient(135deg, var(--primary) 50%, var(--bg) 50%)` }}
              />
              {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
