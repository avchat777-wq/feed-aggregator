import React, { useState, useEffect } from 'react'
import api from '../api'

export default function Logs() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({ status: '', page: 1 })

  useEffect(() => {
    setLoading(true)
    const params = { page: filter.page, per_page: 50 }
    if (filter.status) params.status = filter.status
    api.get('/api/logs', { params }).then(r => setLogs(r.data)).finally(() => setLoading(false))
  }, [filter])

  const statusColors = {
    success: 'bg-green-100 text-green-700',
    partial: 'bg-yellow-100 text-yellow-700',
    fail: 'bg-red-100 text-red-700',
    running: 'bg-blue-100 text-blue-700',
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold">Логи синхронизации</h2>
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={filter.status}
          onChange={e => setFilter(f => ({ ...f, status: e.target.value, page: 1 }))}
        >
          <option value="">Все статусы</option>
          <option value="success">Успешно</option>
          <option value="partial">Частично</option>
          <option value="fail">Ошибка</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border shadow-sm overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              <th className="p-3">Дата</th>
              <th className="p-3">Источник</th>
              <th className="p-3">Статус</th>
              <th className="p-3">Объектов</th>
              <th className="p-3">Новых</th>
              <th className="p-3">Обновл.</th>
              <th className="p-3">Удалено</th>
              <th className="p-3">Ошибок</th>
              <th className="p-3">Время</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {logs.map(l => (
              <tr key={l.id} className="hover:bg-gray-50">
                <td className="p-3 text-xs text-gray-500">{l.started_at ? new Date(l.started_at).toLocaleString('ru') : '—'}</td>
                <td className="p-3">{l.source_id || 'Глобальный'}</td>
                <td className="p-3"><span className={`px-2 py-0.5 rounded text-xs ${statusColors[l.status] || 'bg-gray-100'}`}>{l.status}</span></td>
                <td className="p-3">{l.objects_total}</td>
                <td className="p-3 text-green-600">{l.objects_new > 0 ? `+${l.objects_new}` : '0'}</td>
                <td className="p-3 text-blue-600">{l.objects_updated}</td>
                <td className="p-3 text-red-500">{l.objects_removed > 0 ? `-${l.objects_removed}` : '0'}</td>
                <td className="p-3">{l.errors_count > 0 ? <span className="text-red-500 font-medium">{l.errors_count}</span> : '0'}</td>
                <td className="p-3 text-xs text-gray-400">{l.response_time_ms ? `${l.response_time_ms}ms` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-6 text-center text-gray-400">Загрузка...</div>}
      </div>
    </div>
  )
}
