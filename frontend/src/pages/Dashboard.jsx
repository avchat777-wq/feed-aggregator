import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Activity, Database, AlertTriangle, CheckCircle } from 'lucide-react'
import api from '../api'

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-5">
      <div className="flex items-center gap-3">
        <div className={`p-2.5 rounded-lg ${color}`}>
          <Icon size={20} className="text-white" />
        </div>
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-bold">{value}</p>
        </div>
      </div>
    </div>
  )
}

function SourceHealth({ sources }) {
  const statusColors = { ok: 'bg-green-100 text-green-700', warning: 'bg-yellow-100 text-yellow-700', error: 'bg-red-100 text-red-700', disabled: 'bg-gray-100 text-gray-500' }
  const statusLabels = { ok: 'OK', warning: 'Внимание', error: 'Ошибка', disabled: 'Отключён' }

  return (
    <div className="bg-white rounded-xl shadow-sm border">
      <div className="p-4 border-b"><h3 className="font-semibold">Здоровье источников</h3></div>
      <div className="divide-y">
        {sources.map(s => (
          <div key={s.source_id} className="p-4 flex items-center justify-between">
            <div>
              <p className="font-medium">{s.name}</p>
              <p className="text-sm text-gray-500">{s.developer} · {s.type} · {s.object_count} объектов</p>
            </div>
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${statusColors[s.status]}`}>
              {statusLabels[s.status]}
            </span>
          </div>
        ))}
        {sources.length === 0 && <p className="p-4 text-gray-400">Нет подключённых источников</p>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/dashboard').then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex justify-center py-12"><div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" /></div>
  if (!data) return <p className="text-red-500">Ошибка загрузки</p>

  const chartData = data.sync_history?.map(h => ({
    date: h.started_at ? new Date(h.started_at).toLocaleDateString('ru') : '?',
    total: h.objects_total || 0,
    new: h.objects_new || 0,
    updated: h.objects_updated || 0,
  })).reverse() || []

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Дашборд</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard icon={Database} label="Активных объектов" value={data.active_objects} color="bg-blue-500" />
        <StatCard icon={Activity} label="Источников" value={`${data.active_sources}/${data.total_sources}`} color="bg-green-500" />
        <StatCard icon={CheckCircle} label="Последняя синхр." value={data.last_sync?.status || '—'} color="bg-purple-500" />
        <StatCard icon={AlertTriangle} label="Всего объектов" value={data.total_objects} color="bg-orange-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border p-4">
          <h3 className="font-semibold mb-4">Динамика объектов</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" fontSize={12} />
              <YAxis fontSize={12} />
              <Tooltip />
              <Bar dataKey="total" name="Всего" fill="#3b82f6" />
              <Bar dataKey="new" name="Новых" fill="#22c55e" />
              <Bar dataKey="updated" name="Обновлено" fill="#f59e0b" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <SourceHealth sources={data.sources_health || []} />
      </div>
    </div>
  )
}
