import React, { useState, useEffect } from 'react'
import { Search, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '../api'

export default function Objects() {
  const [objects, setObjects] = useState([])
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ search: '', status: '', developer: '', jk_name: '' })
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [history, setHistory] = useState([])

  const load = () => {
    setLoading(true)
    const params = { page, per_page: 50 }
    if (filters.search) params.search = filters.search
    if (filters.status) params.status = filters.status
    if (filters.developer) params.developer = filters.developer
    if (filters.jk_name) params.jk_name = filters.jk_name
    api.get('/api/objects', { params }).then(r => setObjects(r.data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [page, filters])

  const showHistory = async (obj) => {
    setSelected(obj)
    const { data } = await api.get(`/api/objects/${obj.id}/history`)
    setHistory(data)
  }

  const setFilter = (k, v) => { setFilters(f => ({ ...f, [k]: v })); setPage(1) }

  const statusColors = {
    active: 'bg-green-100 text-green-700',
    booked: 'bg-yellow-100 text-yellow-700',
    sold: 'bg-gray-100 text-gray-500',
    removed: 'bg-red-100 text-red-700',
  }

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Объекты</h2>

      {/* Filters */}
      <div className="bg-white rounded-xl border shadow-sm p-4 mb-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-2.5 text-gray-400" />
          <input
            className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm"
            placeholder="Поиск по ID или номеру квартиры..."
            value={filters.search} onChange={e => setFilter('search', e.target.value)}
          />
        </div>
        <select className="border rounded-lg px-3 py-2 text-sm" value={filters.status} onChange={e => setFilter('status', e.target.value)}>
          <option value="">Все статусы</option>
          <option value="active">Активные</option>
          <option value="booked">Забронированы</option>
          <option value="sold">Проданы</option>
          <option value="removed">Удалены</option>
        </select>
        <input className="border rounded-lg px-3 py-2 text-sm" placeholder="Застройщик" value={filters.developer} onChange={e => setFilter('developer', e.target.value)} />
        <input className="border rounded-lg px-3 py-2 text-sm" placeholder="ЖК" value={filters.jk_name} onChange={e => setFilter('jk_name', e.target.value)} />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border shadow-sm overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              <th className="p-3">ExternalId</th>
              <th className="p-3">ЖК</th>
              <th className="p-3">Кв.</th>
              <th className="p-3">Этаж</th>
              <th className="p-3">Комн.</th>
              <th className="p-3">Площадь</th>
              <th className="p-3">Цена</th>
              <th className="p-3">Статус</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {objects.map(o => (
              <tr key={o.id} className="hover:bg-blue-50 cursor-pointer" onClick={() => showHistory(o)}>
                <td className="p-3 font-mono text-xs">{o.external_id}</td>
                <td className="p-3">{o.jk_name}</td>
                <td className="p-3">{o.flat_number}</td>
                <td className="p-3">{o.floor}{o.floors_total ? `/${o.floors_total}` : ''}</td>
                <td className="p-3">{o.rooms === 0 ? 'Ст.' : o.rooms}</td>
                <td className="p-3">{o.total_area} м²</td>
                <td className="p-3 font-medium">{o.price?.toLocaleString('ru')} ₽</td>
                <td className="p-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${statusColors[o.status] || 'bg-gray-100'}`}>{o.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-8 text-center"><div className="animate-spin h-6 w-6 border-3 border-blue-500 border-t-transparent rounded-full mx-auto" /></div>}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-center gap-4 mt-4">
        <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-30"><ChevronLeft size={16} /></button>
        <span className="text-sm text-gray-500">Стр. {page}</span>
        <button onClick={() => setPage(p => p + 1)} disabled={objects.length < 50} className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-30"><ChevronRight size={16} /></button>
      </div>

      {/* Object detail modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center" onClick={() => setSelected(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-auto m-4" onClick={e => e.stopPropagation()}>
            <div className="p-6 border-b">
              <h3 className="text-lg font-bold">{selected.external_id}</h3>
              <p className="text-gray-500">{selected.developer_name} · {selected.jk_name} · кв. {selected.flat_number}</p>
            </div>
            <div className="p-6 grid grid-cols-2 gap-3 text-sm">
              <div><span className="text-gray-500">Этаж:</span> {selected.floor}/{selected.floors_total || '?'}</div>
              <div><span className="text-gray-500">Комнат:</span> {selected.rooms === 0 ? 'Студия' : selected.rooms}</div>
              <div><span className="text-gray-500">Площадь:</span> {selected.total_area} м²</div>
              <div><span className="text-gray-500">Цена:</span> {selected.price?.toLocaleString('ru')} ₽</div>
              <div><span className="text-gray-500">Цена/м²:</span> {selected.price_per_sqm?.toLocaleString('ru')} ₽</div>
              <div><span className="text-gray-500">Отделка:</span> {selected.decoration || '—'}</div>
              <div><span className="text-gray-500">Тип сделки:</span> {selected.sale_type || '—'}</div>
              <div><span className="text-gray-500">Телефон:</span> {selected.phone}</div>
            </div>
            {history.length > 0 && (
              <div className="p-6 border-t">
                <h4 className="font-semibold mb-3">История изменений</h4>
                <div className="space-y-2">
                  {history.map(h => (
                    <div key={h.id} className="flex items-center gap-3 text-sm">
                      <span className="text-gray-400 text-xs w-36">{new Date(h.changed_at).toLocaleString('ru')}</span>
                      <span className="font-medium">{h.field_name}:</span>
                      <span className="text-red-500 line-through">{h.old_value}</span>
                      <span>→</span>
                      <span className="text-green-600">{h.new_value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="p-4 border-t flex justify-end">
              <button onClick={() => setSelected(null)} className="px-4 py-2 border rounded-lg hover:bg-gray-50">Закрыть</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
