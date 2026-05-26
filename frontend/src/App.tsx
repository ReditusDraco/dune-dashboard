import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ChakraProvider, defaultSystem } from '@chakra-ui/react'
import { AppProvider, useApp } from './stores/AppContext'
import { injectThemeVars } from './themes/inject'
import { useRealtime } from './hooks/useRealtime'
import AppShell from './components/layout/AppShell'
import Overview from './components/overview/Overview'
import PlayerExplorer from './components/players/PlayerExplorer'
import PlayerDetail from './components/players/PlayerDetail'
import GuildManager from './components/guilds/GuildManager'
import Vehicles from './components/vehicles/Vehicles'
import Buildings from './components/buildings/Buildings'
import MapViewer from './components/map/MapViewer'
import Accounts from './components/accounts/Accounts'
import ServerControl from './components/server/ServerControl'
import AdminTools from './components/admin/AdminTools'
import ChatMonitor from './components/chat/ChatMonitor'
import Terminal from './components/shell/Terminal'
import FileBrowser from './components/files/FileBrowser'
import Director from './components/director/Director'
import Settings from './components/settings/Settings'
import Experimental from './components/experimental/Experimental'

function RealtimeInit() {
  useRealtime()
  return null
}

function ThemedApp() {
  const { state } = useApp()

  useEffect(() => {
    injectThemeVars(state.faction, state.colorMode)
  }, [state.faction, state.colorMode])

  return (
    <ChakraProvider value={defaultSystem}>
      <BrowserRouter>
        <RealtimeInit />
        <AppShell>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/players" element={<PlayerExplorer />} />
            <Route path="/players/:accountId" element={<PlayerDetail />} />
            <Route path="/guilds" element={<GuildManager />} />
            <Route path="/vehicles" element={<Vehicles />} />
            <Route path="/buildings" element={<Buildings />} />
            <Route path="/map" element={<MapViewer />} />
            <Route path="/accounts" element={<Accounts />} />
            <Route path="/server" element={<ServerControl />} />
            <Route path="/admin" element={<AdminTools />} />
            <Route path="/chat" element={<ChatMonitor />} />
            <Route path="/shell" element={<Terminal />} />
            <Route path="/files" element={<FileBrowser />} />
            <Route path="/director" element={<Director />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/experimental" element={<Experimental />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </ChakraProvider>
  )
}

export default function App() {
  return (
    <AppProvider>
      <ThemedApp />
    </AppProvider>
  )
}
