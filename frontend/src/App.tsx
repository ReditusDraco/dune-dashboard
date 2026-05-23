import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppProvider } from './stores/AppContext'
import { useRealtime } from './hooks/useRealtime'
import AppShell from './components/layout/AppShell'
import Overview from './components/overview/Overview'
import PlayerExplorer from './components/players/PlayerExplorer'
import GuildManager from './components/guilds/GuildManager'
import ServerControl from './components/server/ServerControl'
import AdminTools from './components/admin/AdminTools'
import ChatMonitor from './components/chat/ChatMonitor'
import Terminal from './components/shell/Terminal'

function RealtimeInit() {
  useRealtime()
  return null
}

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <RealtimeInit />
        <AppShell>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/players" element={<PlayerExplorer />} />
            <Route path="/guilds" element={<GuildManager />} />
            <Route path="/server" element={<ServerControl />} />
            <Route path="/admin" element={<AdminTools />} />
            <Route path="/chat" element={<ChatMonitor />} />
            <Route path="/shell" element={<Terminal />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </AppProvider>
  )
}

export default App
