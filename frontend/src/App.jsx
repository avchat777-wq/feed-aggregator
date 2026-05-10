import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Database, Settings, FileText,
  Bell, Download, Users, LogOut, Menu, X
} from 'lucide-react'
import api from './api'
import Dashboard from './pages/Dashboard'
import Sources from './pages/Sources'
import Objects from './pages/Objects'
import Logs from './pages/Logs'
import Mappings from './pages/Mappings'
import Feed from './pages/Feed'
import Alerts from './pages/Alerts'
import Login from './pages/Login'

function Sidebar({ open, setOpen }) {
  const location = useLocation()
  const links = [
    { to: '/', icon: LayoutDashboard, label: 'Дашборд' },
    { to: '/sources', icon: Database, label: 'Источники' },
    { to: '/mappings', icon: Settings, label: 'Маппинг' },
    { to: '/objects', icon: FileText, label: 'Объекты' },
    { to: '/logs', icon: FileText, label: 'Логи' },
    { to: '/alerts', icon: Bell, label: 'Уведомления' },
    { to: '/feed', icon: Download, label: 'Выходной фид' },
  ]

  return (
    <aside className={`
      fixed inset-y-0 left-0 z-30 w-64 bg-slate-800 text-white transform transition-transform
      ${open ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 lg:static
    `}>
      <div className="flex items-center justify-between p-4 border-b border-slate-700">
        <h1 className="text-lg font-bold">Feed Aggregator</h1>
        <button onClick={() => setOpen(false)} className="lg:hidden">
          <X size={20} />
        </button>
      </div>
      <nav className="p-2">
        {links.map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            onClick={() => setOpen(false)}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition
              ${location.pathname === to
                ? 'bg-blue-600 text-white'
                : 'text-slate-300 hover:bg-slate-700'
              }`}
          >
            <Icon size={18} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
      <div className="absolute bottom-0 w-full p-4 border-t border-slate-700">
        <button
          onClick={() => { localStorage.removeItem('token'); window.location.href = '/login' }}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition"
        >
          <LogOut size={18} /> Выйти
        </button>
      </div>
    </aside>
  )
}

function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex min-h-screen">
      <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-20 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}
      <main className="flex-1 min-w-0">
        <header className="bg-white shadow-sm border-b px-4 py-3 flex items-center lg:hidden">
          <button onClick={() => setSidebarOpen(true)}>
            <Menu size={24} />
          </button>
          <span className="ml-3 font-semibold">Feed Aggregator</span>
        </header>
        <div className="p-4 lg:p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sources" element={<Sources />} />
            <Route path="/objects" element={<Objects />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/mappings" element={<Mappings />} />
            <Route path="/feed" element={<Feed />} />
            <Route path="/alerts" element={<Alerts />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/*" element={
          <ProtectedRoute><Layout /></ProtectedRoute>
        } />
      </Routes>
    </BrowserRouter>
  )
}
