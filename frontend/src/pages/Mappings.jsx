import React, { useState, useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import api from '../api'

const TARGET_FIELDS = [
  'source_object_id', 'developer_name', 'jk_name', 'jk_id_cian',
  'house_name', 'section_number', 'flat_number', 'floor', 'floors_total',
  'rooms', 'total_area', 'living_area', 'kitchen_area', 'price',
  'sale_type', 'decoration', 'description', 'photos', 'phone', 'status',
  'latitude', 'longitude',
]

export default function Mappings() {
  const [mappings, setMappings] = useState([])
  const [sources, setSources] = useState([])
  const [selectedSource, setSelectedSource] = useState('')
  const [newMapping, setNewMapping] = useState({ source_field: '', target_field: 'flat_number', transform_rule: '' })
  const [loading, setLoading] = useState(true)

  const load = () => {
    Promise.all([
      api.get('/api/mappings', { params: selectedSource ? { source_id: selectedSource } : {} }),
      api.get('/api/sources'),
    ]).then(([m, s]) => {
      setMappings(m.data)
      setSources(s.data.filter(src => src.type === 'custom_xml' || src.type === 'excel'))
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [selectedSource])

  const handleAdd = async () => {
    if (!selectedSource || !newMapping.source_field || !newMapping.target_field) return
    await api.post('/api/mappings', { ...newMapping, source_id: parseInt(selectedSource) })
    setNewMapping({ source_field: '', target_field: 'flat_number', transform_rule: '' })
    load()
  }

  const handleDelete = async (id) => {
    await api.delete(`/api/mappings/${id}`)
    load()
  }

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Маппинг полей</h2>
      <p className="text-gray-500 mb-4">Настройка соответствия полей для источников типа "Произвольный XML" и "Excel".</p>

      <div className="mb-4">
        <select
          className="border rounded-lg px-3 py-2"
          value={selectedSource}
          onChange={e => setSelectedSource(e.target.value)}
        >
          <option value="">Выберите источник</option>
          {sources.map(s => <option key={s.id} value={s.id}>{s.name} ({s.type})</option>)}
        </select>
      </div>

      {selectedSource && (
        <div className="bg-white rounded-xl border shadow-sm p-4 mb-4">
          <h3 className="font-semibold mb-3">Добавить маппинг</h3>
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="block text-xs font-medium mb-1">Поле источника (XPath / Столбец)</label>
              <input
                className="border rounded-lg px-3 py-2 text-sm w-64"
                placeholder="Напр: ./Price или цена"
                value={newMapping.source_field}
                onChange={e => setNewMapping(m => ({ ...m, source_field: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Целевое поле</label>
              <select
                className="border rounded-lg px-3 py-2 text-sm"
                value={newMapping.target_field}
                onChange={e => setNewMapping(m => ({ ...m, target_field: e.target.value }))}
              >
                {TARGET_FIELDS.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Трансформация (опц.)</label>
              <input
                className="border rounded-lg px-3 py-2 text-sm w-48"
                placeholder="regex, формула..."
                value={newMapping.transform_rule}
                onChange={e => setNewMapping(m => ({ ...m, transform_rule: e.target.value }))}
              />
            </div>
            <button onClick={handleAdd} className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
              <Plus size={14} /> Добавить
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border shadow-sm overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              <th className="p-3">Источник</th>
              <th className="p-3">Поле источника</th>
              <th className="p-3">→</th>
              <th className="p-3">Целевое поле</th>
              <th className="p-3">Трансформация</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {mappings.map(m => (
              <tr key={m.id} className="hover:bg-gray-50">
                <td className="p-3">{m.source_id}</td>
                <td className="p-3 font-mono text-xs">{m.source_field}</td>
                <td className="p-3 text-gray-400">→</td>
                <td className="p-3 font-mono text-xs">{m.target_field}</td>
                <td className="p-3 text-xs text-gray-500">{m.transform_rule || '—'}</td>
                <td className="p-3">
                  <button onClick={() => handleDelete(m.id)} className="p-1 hover:bg-red-50 rounded">
                    <Trash2 size={14} className="text-red-400" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-6 text-center text-gray-400">Загрузка...</div>}
        {!loading && mappings.length === 0 && <p className="p-6 text-center text-gray-400">Нет маппингов</p>}
      </div>
    </div>
  )
}
