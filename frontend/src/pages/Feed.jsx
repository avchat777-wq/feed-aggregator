import React, { useState, useEffect } from 'react'
import { Download, RefreshCw, Link, Eye } from 'lucide-react'
import api from '../api'

export default function Feed() {
  const [feedUrl, setFeedUrl] = useState('')
  const [preview, setPreview] = useState(null)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    api.get('/api/feed/url').then(r => setFeedUrl(r.data.url))
    api.get('/api/feed/preview').then(r => setPreview(r.data))
  }, [])

  const triggerSync = async () => {
    setSyncing(true)
    try {
      await api.post('/api/feed/sync')
      alert('Синхронизация запущена в фоне.')
    } catch (e) {
      alert('Ошибка: ' + e.message)
    }
    setSyncing(false)
  }

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Выходной фид</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h3 className="font-semibold mb-3 flex items-center gap-2"><Link size={16} /> URL фида</h3>
          <div className="bg-gray-50 rounded-lg p-3 font-mono text-sm break-all">{feedUrl}</div>
          <p className="text-xs text-gray-400 mt-2">Этот URL указывается в настройках CRM Intrum</p>
        </div>

        <div className="bg-white rounded-xl border shadow-sm p-5">
          <h3 className="font-semibold mb-3">Информация</h3>
          {preview && preview.exists ? (
            <div className="text-sm space-y-1">
              <p>Размер: {(preview.size_bytes / 1024).toFixed(1)} KB</p>
            </div>
          ) : (
            <p className="text-gray-400 text-sm">Фид ещё не сгенерирован</p>
          )}
        </div>
      </div>

      <div className="flex gap-3 mb-6">
        <button
          onClick={triggerSync}
          disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
        >
          <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
          {syncing ? 'Синхронизация...' : 'Запустить синхронизацию'}
        </button>
        <a
          href="/api/feed/download"
          className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-50 transition"
        >
          <Download size={16} /> Скачать XML
        </a>
      </div>

      {preview && preview.content && (
        <div className="bg-white rounded-xl border shadow-sm">
          <div className="p-4 border-b flex items-center gap-2">
            <Eye size={16} />
            <h3 className="font-semibold">Предпросмотр фида</h3>
          </div>
          <pre className="p-4 text-xs overflow-auto max-h-96 bg-gray-50">{preview.content}</pre>
        </div>
      )}
    </div>
  )
}