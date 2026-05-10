import React, { useState, useEffect } from 'react'
import { Bell, Send } from 'lucide-react'
import api from '../api'

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = {}
    if (filter) params.type = filter
    api.get('/api/notifications/alerts', { params }).then(r => setAlerts(r.data)).finally(() => setLoading(false))
  }, [filter])

  const sendTest = async () => {
    const { data } = await api.post('/api/notifications/test')
    alert(data.success ? 'Тестовое уведомление отправлено!' : 'Ошибка отправки. Проверьте настройки бота.')
  }

  const typeColors = {
    CRITICAL: 'bg-red-100 text-red-700 border-red-200',
    WARNING: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    INFO: 'bg-blue-100 text-blue-700 border-blue-200',
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Уведомления</h2>
        <div className="flex gap-2">
          <select className="border rounded-lg px-3 py-2 text-sm" value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="">Все типы</option>
            <option value="CRITICAL">Critical</option>
            <option value="WARNING">Warning</option>
            <option value="INFO">Info</option>
          </select>
          <button onClick={sendTest} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm transition">
            <Send size={14} /> Тест
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {alerts.map(a => (
          <div key={a.id} className={`rounded-xl border p-4 ${typeColors[a.type] || 'bg-gray-50'}`}>
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-sm">{a.type}</span>
              <span className="text-xs opacity-70">{a.sent_at ? new Date(a.sent_at).toLocaleString('ru') : ''}</span>
            </div>
            <p className="text-sm whitespace-pre-wrap">{a.message}</p>
          </div>
        ))}
        {loading && <div className="text-center py-8 text-gray-400">Загрузка...</div>}
        {!loading && alerts.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <Bell size={32} className="mx-auto mb-2 opacity-30" />
            <p>Нет уведомлений</p>
          </div>
        )}
      </div>
    </div>
  )
}
