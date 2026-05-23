import { ReactNode } from 'react'
import NavBar from './NavBar'
import ToastProvider from '../common/ToastProvider'

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-text-primary">
      <NavBar />
      <main className="p-6 max-w-[1600px] mx-auto">
        <ToastProvider />
        {children}
      </main>
    </div>
  )
}
