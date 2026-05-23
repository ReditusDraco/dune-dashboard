import React, { createContext, useContext, useReducer, useEffect } from 'react'

interface AppState {
  user: string | null
  theme: string
  connectionStatus: {
    database: boolean
    ssh: boolean
    bgd: boolean
    rmq: boolean
  }
  toasts: Toast[]
}

interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
}

type Action =
  | { type: 'SET_USER'; payload: string | null }
  | { type: 'SET_THEME'; payload: string }
  | { type: 'SET_CONNECTION'; payload: Partial<AppState['connectionStatus']> }
  | { type: 'ADD_TOAST'; payload: Omit<Toast, 'id'> }
  | { type: 'REMOVE_TOAST'; payload: number }

const initialState: AppState = {
  user: null,
  theme: localStorage.getItem('dune-theme') || 'emperor',
  connectionStatus: {
    database: true,
    ssh: true,
    bgd: true,
    rmq: true,
  },
  toasts: [],
}

let toastId = 0

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_USER':
      return { ...state, user: action.payload }
    case 'SET_THEME':
      return { ...state, theme: action.payload }
    case 'SET_CONNECTION':
      return { ...state, connectionStatus: { ...state.connectionStatus, ...action.payload } }
    case 'ADD_TOAST':
      return { ...state, toasts: [...state.toasts.slice(-2), { ...action.payload, id: ++toastId }] }
    case 'REMOVE_TOAST':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.payload) }
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
    document.documentElement.dataset.theme = state.theme
    localStorage.setItem('dune-theme', state.theme)
  }, [state.theme])

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
