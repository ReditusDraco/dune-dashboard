import { createContext, useContext, useReducer, useEffect } from 'react'
import type { FactionKey } from '../themes/palettes'
import { toaster } from '../toaster'

interface AppState {
  user: string | null
  faction: FactionKey
  colorMode: 'day' | 'night'
  connectionStatus: {
    database: boolean
    ssh: boolean
    bgd: boolean
    rmq: boolean
  }
}

type Action =
  | { type: 'SET_USER'; payload: string | null }
  | { type: 'SET_FACTION'; payload: FactionKey }
  | { type: 'SET_COLOR_MODE'; payload: 'day' | 'night' }
  | { type: 'SET_CONNECTION'; payload: Partial<AppState['connectionStatus']> }
  | { type: 'ADD_TOAST'; payload: { message: string; type: 'success' | 'error' | 'warning' | 'info' } }

function loadStoredFaction(): FactionKey {
  try {
    const stored = localStorage.getItem('dune-faction')
    if (stored) return stored as FactionKey
  } catch {}
  return 'fremen'
}

function loadStoredColorMode(): 'day' | 'night' {
  try {
    const stored = localStorage.getItem('dune-color-mode')
    if (stored === 'day' || stored === 'night') return stored
  } catch {}
  return 'night'
}

const initialState: AppState = {
  user: null,
  faction: loadStoredFaction(),
  colorMode: loadStoredColorMode(),
  connectionStatus: {
    database: true,
    ssh: true,
    bgd: true,
    rmq: true,
  },
}

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_USER':
      return { ...state, user: action.payload }
    case 'SET_FACTION':
      return { ...state, faction: action.payload }
    case 'SET_COLOR_MODE':
      return { ...state, colorMode: action.payload }
    case 'SET_CONNECTION':
      return { ...state, connectionStatus: { ...state.connectionStatus, ...action.payload } }
    case 'ADD_TOAST':
      toaster[action.payload.type]({
        title: action.payload.message,
        duration: 4000,
      })
      return state
    default:
      return state
  }
}

const AppContext = createContext<{
  state: AppState
  dispatch: React.Dispatch<Action>
} | null>(null)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  useEffect(() => {
    localStorage.setItem('dune-faction', state.faction)
  }, [state.faction])

  useEffect(() => {
    localStorage.setItem('dune-color-mode', state.colorMode)
  }, [state.colorMode])

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
