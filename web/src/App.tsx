import { useState, useEffect } from 'react'
import { Route, Routes } from 'react-router'
import { useAuth, useLogin } from './api/client'
import { Button } from './components/ui'
import Sidebar from './components/Sidebar'
import Browse from './pages/Browse'
import Errors from './pages/Errors'
import Inbox from './pages/Inbox'
import Settings from './pages/Settings'
import Sources from './pages/Sources'
import System from './pages/System'
import Tasks from './pages/Tasks'
import Today from './pages/Today'

function AuthBanner() {
  const auth = useAuth()
  const login = useLogin()
  if (auth.error) {
    return (
      <div className="bg-red-600 px-4 py-2 text-sm text-white">
        Can't reach the backend ({auth.error.message}). Is <code>campus serve</code> running?
      </div>
    )
  }
  const a = auth.data
  if (!a || a.state !== 'login_required') return null
  const hosts = Object.entries(a.hosts).filter(([, h]) => h.state === 'login_required').map(([h]) => h)
  return (
    <div className="flex flex-wrap items-center gap-3 bg-amber-100 px-4 py-2 text-sm text-amber-900">
      <span>Brightspace sign-in needed for {hosts.join(', ')}.</span>
      {a.login_in_progress ? (
        <span className="font-medium">Sign-in window open on this computer — finish there…</span>
      ) : (
        <Button variant="primary" disabled={login.isPending || !!a.busy} onClick={() => login.mutate()}>
          Sign in
        </Button>
      )}
    </div>
  )
}

export default function App() {
  const [sidebarExpanded, setSidebarExpanded] = useState(() => {
    try { return localStorage.getItem('sidebar-expanded') !== 'false' } catch { return true }
  })

  useEffect(() => {
    try { localStorage.setItem('sidebar-expanded', String(sidebarExpanded)) } catch { /* ignore */ }
  }, [sidebarExpanded])

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar isExpanded={sidebarExpanded} onToggle={() => setSidebarExpanded(v => !v)} />
      <div className={`flex flex-1 flex-col transition-all duration-300 ${sidebarExpanded ? 'pl-56' : 'pl-14'}`}>
        <AuthBanner />
        <main className="flex-1 p-6">
          <div className="mx-auto max-w-7xl">
            <Routes>
              <Route path="/" element={<Today />} />
              <Route path="/inbox" element={<Inbox />} />
              <Route path="/tasks" element={<Tasks />} />
              <Route path="/items" element={<Browse />} />
              <Route path="/sources" element={<Sources />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/errors" element={<Errors />} />
              <Route path="/system" element={<System />} />
              <Route path="*" element={<p>Not found.</p>} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  )
}
