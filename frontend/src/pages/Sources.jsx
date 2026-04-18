import { useState, useEffect } from "react";
import api from "../api";

// ── Constants ─────────────────────────────────────────────────────────────────

const SOURCE_TYPES = [
  { value: "domclick",      label: "DomClick",           group: "DomClick" },
  { value: "domclick_pro",  label: "DomClick Pro",        group: "DomClick" },
  { value: "avito",         label: "Avito",               group: "Avito" },
  { value: "avito_builder", label: "Avito Builder",        group: "Avito" },
  { value: "yandex",        label: "Яндекс.Недвижимость", group: "Яндекс" },
  { value: "cian",          label: "ЦИАН",                group: "ЦИАН" },
  { value: "custom_xml",    label: "Custom XML",           group: "Прочее" },
  { value: "excel",         label: "Excel / CSV",          group: "Прочее" },
];

const STATUS_META = {
  ok:      { label: "OK",      bg: "bg-green-100",  text: "text-green-800",  dot: "bg-green-500"  },
  warning: { label: "Кэш",    bg: "bg-yellow-100", text: "text-yellow-800", dot: "bg-yellow-500" },
  error:   { label: "Ошибка", bg: "bg-red-100",    text: "text-red-800",    dot: "bg-red-500"    },
  unknown: { label: "—",      bg: "bg-gray-100",   text: "text-gray-600",   dot: "bg-gray-400"   },
};

// ── StatusBadge ───────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.unknown;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${m.bg} ${m.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />
      {m.label}
    </span>
  );
}

// ── JK Breakdown panel ────────────────────────────────────────────────────────

function JkBreakdown({ sourceId }) {
  const [stats, setStats]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/api/sources/${sourceId}/jk-stats`)
      .then(r => setStats(r.data))
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, [sourceId]);

  if (loading) return <p className="text-sm text-gray-400 py-2">Загрузка...</p>;
  if (!stats || stats.jk_stats.length === 0)
    return <p className="text-sm text-gray-400 py-2">Нет активных объектов по ЖК</p>;

  return (
    <div className="mt-3">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        ЖК в этом источнике ({stats.jk_stats.length})
      </p>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50 text-xs text-gray-500 uppercase">
            <th className="text-left py-1 px-2">ЖК</th>
            <th className="text-right py-1 px-2">Кв.</th>
            <th className="text-right py-1 px-2">Мин. цена</th>
            <th className="text-right py-1 px-2">Макс. цена</th>
          </tr>
        </thead>
        <tbody>
          {stats.jk_stats.map(row => (
            <tr key={row.jk_name} className="border-t border-gray-100">
              <td className="py-1.5 px-2 font-medium">{row.jk_name || "—"}</td>
              <td className="py-1.5 px-2 text-right">{row.object_count}</td>
              <td className="py-1.5 px-2 text-right text-gray-600">
                {row.min_price.toLocaleString("ru-RU")} ₽
              </td>
              <td className="py-1.5 px-2 text-right text-gray-600">
                {row.max_price.toLocaleString("ru-RU")} ₽
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── DiagnosticsPanel ──────────────────────────────────────────────────────────

const CHECK_LABELS = {
  url_set:       "URL задан",
  dns:           "DNS resolve",
  http_status:   "HTTP статус (200)",
  response_time: "Время ответа (< 5с)",
  not_empty:     "Файл не пустой",
  xml_valid:     "XML валиден",
};

function DiagnosticsPanel({ sourceId, onClose }) {
  const [result, setResult]   = useState(null);
  const [running, setRunning] = useState(true);

  useEffect(() => {
    api.post(`/api/sources/${sourceId}/diagnostics`)
      .then(r => setResult(r.data))
      .catch(e => setResult({ error: e.message }))
      .finally(() => setRunning(false));
  }, [sourceId]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-gray-800 text-lg">Диагностика источника</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        {running && (
          <div className="text-center py-8 text-gray-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3" />
            Проверка...
          </div>
        )}

        {result?.error && <p className="text-red-600 text-sm">{result.error}</p>}

        {result && !result.error && (
          <>
            <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
              result.passed ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
            }`}>
              {result.passed ? "✅ Все проверки пройдены" : "❌ Есть проблемы"}
              <span className="ml-2 text-xs font-normal opacity-70">({result.duration_ms} мс)</span>
            </div>
            <ul className="space-y-2">
              {Object.entries(result.checks).map(([key, val]) => (
                <li key={key} className="flex items-start gap-2 text-sm">
                  <span className={val.ok ? "text-green-500 font-bold" : "text-red-500 font-bold"}>
                    {val.ok ? "✓" : "✗"}
                  </span>
                  <span className="text-gray-600 w-44 shrink-0">
                    {CHECK_LABELS[key] || key}
                  </span>
                  <span className="text-gray-400 text-xs">{val.detail}</span>
                </li>
              ))}
            </ul>
          </>
        )}

        <button
          onClick={onClose}
          className="mt-6 w-full bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg py-2 text-sm"
        >
          Закрыть
        </button>
      </div>
    </div>
  );
}

// ── Source Form modal ─────────────────────────────────────────────────────────

function SourceForm({ source, onSave, onClose }) {
  const [form, setForm] = useState(
    source || {
      name: "", developer_name: "", type: "domclick",
      url: "", is_active: true, phone_override: "",
    }
  );
  const [saving, setSaving] = useState(false);

  const handleSubmit = async e => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form, phone_override: form.phone_override || null };
      if (source?.id) {
        await api.put(`/api/sources/${source.id}`, payload);
      } else {
        await api.post("/api/sources", payload);
      }
      onSave();
    } catch (err) {
      alert(err.response?.data?.detail || "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  };

  const f = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 overflow-y-auto max-h-screen">
        <div className="flex justify-between items-center mb-5">
          <h3 className="font-semibold text-gray-800 text-lg">
            {source ? "Редактировать источник" : "Добавить источник"}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название *</label>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.name}
              onChange={e => f("name", e.target.value)}
              required
              placeholder="Т-Строй — все ЖК"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Застройщик *</label>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.developer_name}
              onChange={e => f("developer_name", e.target.value)}
              required
              placeholder="Т-Строй"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Тип фида *</label>
            <select
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.type}
              onChange={e => f("type", e.target.value)}
            >
              {SOURCE_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.group} — {t.label}</option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              DomClick: domoplaner.ru, profitbase.ru, vtcrm, barnaul-gi.ru, alg22.ru и др.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">URL фида</label>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.url || ""}
              onChange={e => f("url", e.target.value)}
              placeholder="https://..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Телефон (переопределить)
            </label>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={form.phone_override || ""}
              onChange={e => f("phone_override", e.target.value)}
              placeholder="+73852000000"
            />
            <p className="text-xs text-gray-400 mt-1">
              Заменяет телефон из фида для всех объектов этого источника.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={form.is_active}
              onChange={e => f("is_active", e.target.checked)}
              className="rounded"
            />
            <label htmlFor="is_active" className="text-sm text-gray-700">Активен</label>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50"
            >
              {saving ? "Сохранение..." : "Сохранить"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg py-2 text-sm"
            >
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Test Result modal ─────────────────────────────────────────────────────────

function TestResultModal({ result, onClose }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-gray-800 text-lg">Результат тестового парсинга</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${
          result.success ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
        }`}>
          {result.success
            ? `✅ Спарсено объектов: ${result.total_parsed}`
            : `❌ Ошибка: ${result.error}`}
        </div>

        {result.jk_names_found?.length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-semibold text-gray-700 mb-2">
              ЖК найдены в фиде ({result.jk_names_found.length}):
            </p>
            <div className="flex flex-wrap gap-2">
              {result.jk_names_found.map(name => (
                <span key={name} className="bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded">
                  {name}
                </span>
              ))}
            </div>
          </div>
        )}

        {result.errors?.length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-semibold text-red-700 mb-1">
              Ошибки парсинга ({result.errors.length}):
            </p>
            <ul className="text-xs text-red-600 space-y-1">
              {result.errors.map((e, i) => <li key={i}>• {e}</li>)}
            </ul>
          </div>
        )}

        {result.preview?.length > 0 && (
          <div className="overflow-x-auto">
            <p className="text-sm font-semibold text-gray-700 mb-2">Первые объекты:</p>
            <table className="text-xs w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 text-gray-500">
                  {["ID", "ЖК", "Корпус", "Кв.", "Эт.", "Комн.", "Площ.", "Цена"].map(h => (
                    <th key={h} className="px-2 py-1.5 text-left border-b">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.preview.map((obj, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-2 py-1.5 font-mono">{obj.source_object_id}</td>
                    <td className="px-2 py-1.5">{obj.jk_name}</td>
                    <td className="px-2 py-1.5">{obj.house_name || "—"}</td>
                    <td className="px-2 py-1.5">{obj.flat_number}</td>
                    <td className="px-2 py-1.5">{obj.floor}</td>
                    <td className="px-2 py-1.5">{obj.rooms}</td>
                    <td className="px-2 py-1.5">{obj.total_area} м²</td>
                    <td className="px-2 py-1.5">
                      {Number(obj.price).toLocaleString("ru-RU")} ₽
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <button
          onClick={onClose}
          className="mt-5 w-full bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg py-2 text-sm"
        >
          Закрыть
        </button>
      </div>
    </div>
  );
}

// ── Raw XML tags modal ────────────────────────────────────────────────────────

function ContextBlock({ label, info }) {
  if (!info) return null;
  const hasAttrs = info.attrs && Object.keys(info.attrs).length > 0;
  const hasChildren = info.direct_text_children && Object.keys(info.direct_text_children).length > 0;
  if (!hasAttrs && !hasChildren) return (
    <div className="mb-2 text-xs text-gray-400 italic">
      &lt;{info.tag}&gt; — атрибутов и текстовых дочерних тегов не найдено
    </div>
  );
  return (
    <div className="mb-3">
      <div className="text-xs font-semibold text-gray-500 mb-1">
        &lt;{info.tag}&gt;
      </div>
      {hasAttrs && Object.entries(info.attrs).map(([k, v]) => (
        <div key={k} className="flex gap-2 text-xs py-0.5">
          <span className="font-mono text-purple-700 w-40 shrink-0">{info.tag}[@{k}]</span>
          <span className="text-gray-700">{v}</span>
        </div>
      ))}
      {hasChildren && Object.entries(info.direct_text_children).map(([k, v]) => (
        <div key={k} className="flex gap-2 text-xs py-0.5">
          <span className="font-mono text-green-700 w-40 shrink-0">{info.tag}/{k}</span>
          <span className="text-gray-700">{v}</span>
        </div>
      ))}
    </div>
  );
}

function RawTagsModal({ result, onClose }) {
  if (!result) return null;
  const hasParentCtx = result.parent_context && result.parent_context.length > 0;
  const rootHasData = result.root_info &&
    (Object.keys(result.root_info.attrs || {}).length > 0 ||
     Object.keys(result.root_info.direct_text_children || {}).length > 0);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-gray-800 text-lg">Теги XML в фиде</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
        </div>

        {result.error && !result.fields && (
          <div className="bg-red-50 text-red-700 px-4 py-3 rounded-lg text-sm mb-4">
            {result.error}
          </div>
        )}

        <div className="mb-3 text-sm text-gray-500">
          Корневой тег: <code className="bg-gray-100 px-1 rounded">&lt;{result.root_tag}&gt;</code>
          {result.object_tag && (
            <> → объект: <code className="bg-gray-100 px-1 rounded">&lt;{result.object_tag}&gt;</code>
            <span className="ml-2 text-gray-400">({result.total_objects} шт.)</span></>
          )}
        </div>

        {/* Parent context — где ищется название ЖК */}
        {(hasParentCtx || rootHasData) && (
          <div className="mb-4 bg-amber-50 border border-amber-200 rounded-lg p-3">
            <div className="text-xs font-semibold text-amber-700 mb-2">
              🔍 Родительские теги (здесь может быть название ЖК)
            </div>
            {hasParentCtx && result.parent_context.map((ctx, i) => (
              <ContextBlock key={i} info={ctx} />
            ))}
            {rootHasData && <ContextBlock info={result.root_info} />}
          </div>
        )}

        {/* Flat-level fields */}
        {result.fields && Object.keys(result.fields).length > 0 ? (
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-xs text-gray-500 uppercase">
                <th className="text-left py-1.5 px-3 border-b">Тег</th>
                <th className="text-left py-1.5 px-3 border-b">Значение (первый объект)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(result.fields).map(([tag, val]) => (
                <tr key={tag} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-1.5 px-3 font-mono text-blue-700 text-xs">{tag}</td>
                  <td className="py-1.5 px-3 text-gray-700">{val}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-gray-400">Поля не найдены</p>
        )}

        <button
          onClick={onClose}
          className="mt-5 w-full bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg py-2 text-sm"
        >
          Закрыть
        </button>
      </div>
    </div>
  );
}

// ── Source card ───────────────────────────────────────────────────────────────

function SourceCard({ source, onEdit, onDelete, onDiagnostics, onTest, onRawTags }) {
  const [expanded, setExpanded] = useState(false);
  const typeLabel = SOURCE_TYPES.find(t => t.value === source.type)?.label || source.type;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-gray-900 truncate">{source.name}</h3>
              <StatusBadge status={source.status || "unknown"} />
              {!source.is_active && (
                <span className="text-xs bg-gray-100 text-gray-400 px-2 py-0.5 rounded-full">
                  Выключен
                </span>
              )}
            </div>
            <p className="text-sm text-gray-500 mt-0.5">{source.developer_name}</p>
          </div>
          <span className="shrink-0 text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded font-medium">
            {typeLabel}
          </span>
        </div>

        {/* URL */}
        {source.url && (
          <p className="mt-2 text-xs text-gray-400 truncate" title={source.url}>
            {source.url}
          </p>
        )}

        {/* Stats */}
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-gray-600">
          {source.last_object_count != null && (
            <span>
              <span className="font-semibold">{source.last_object_count.toLocaleString("ru-RU")}</span> объектов
            </span>
          )}
          {source.last_sync_at && (
            <span className="text-xs text-gray-400">
              {new Date(source.last_sync_at).toLocaleString("ru-RU")}
            </span>
          )}
          {source.consecutive_failures > 0 && (
            <span className="text-xs text-red-500">
              ⚠ {source.consecutive_failures} ошибок подряд
            </span>
          )}
        </div>

        {/* Cache warning */}
        {source.cache_last_success_at && source.status === "warning" && (
          <p className="mt-1 text-xs text-yellow-600">
            🗂 Работает по кэшу от {new Date(source.cache_last_success_at).toLocaleString("ru-RU")}
          </p>
        )}

        {/* Action buttons */}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => onDiagnostics(source)}
            className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600"
          >
            🔍 Диагностика
          </button>
          <button
            onClick={() => onTest(source)}
            className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600"
          >
            ▶ Тест
          </button>
          <button
            onClick={() => setExpanded(v => !v)}
            className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600"
          >
            {expanded ? "▲ Скрыть ЖК" : "▼ ЖК в фиде"}
          </button>
          <button
            onClick={() => onRawTags(source)}
            className="text-xs px-3 py-1.5 rounded-lg border border-purple-200 hover:bg-purple-50 text-purple-600"
            title="Показать теги XML для диагностики"
          >
            🏷 Теги XML
          </button>
          <button
            onClick={() => onEdit(source)}
            className="text-xs px-3 py-1.5 rounded-lg border border-blue-200 hover:bg-blue-50 text-blue-600"
          >
            ✏ Изменить
          </button>
          <button
            onClick={() => onDelete(source)}
            className="text-xs px-3 py-1.5 rounded-lg border border-red-200 hover:bg-red-50 text-red-600"
          >
            🗑 Удалить
          </button>
        </div>

        {/* Expandable JK breakdown */}
        {expanded && <JkBreakdown sourceId={source.id} />}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Sources() {
  const [sources, setSources]         = useState([]);
  const [loading, setLoading]         = useState(true);
  const [showForm, setShowForm]       = useState(false);
  const [editSource, setEditSource]   = useState(null);
  const [diagSource, setDiagSource]     = useState(null);
  const [testResult, setTestResult]     = useState(null);
  const [testLoading, setTestLoading]   = useState(false);
  const [rawTagsResult, setRawTagsResult] = useState(null);
  const [rawTagsLoading, setRawTagsLoading] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/api/sources")
      .then(r => setSources(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleDelete = async source => {
    if (!confirm(`Удалить источник «${source.name}»?`)) return;
    await api.delete(`/api/sources/${source.id}`);
    load();
  };

  const handleTest = async source => {
    setTestLoading(true);
    try {
      const r = await api.post(`/api/sources/${source.id}/test`);
      setTestResult(r.data);
    } catch (e) {
      setTestResult({ success: false, error: e.message });
    } finally {
      setTestLoading(false);
    }
  };

  const handleRawTags = async source => {
    setRawTagsLoading(true);
    try {
      const r = await api.get(`/api/sources/${source.id}/raw-tags`);
      setRawTagsResult(r.data);
    } catch (e) {
      setRawTagsResult({ error: e.message });
    } finally {
      setRawTagsLoading(false);
    }
  };

  const activeSources = sources.filter(s => s.is_active);
  const okCount       = sources.filter(s => s.status === "ok").length;
  const warnCount     = sources.filter(s => s.status === "warning").length;
  const errorCount    = sources.filter(s => s.status === "error").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Источники</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Каналы получения данных от застройщиков. Один источник может содержать несколько ЖК.
          </p>
        </div>
        <button
          onClick={() => { setEditSource(null); setShowForm(true); }}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Добавить
        </button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: "Всего",    value: sources.length,       color: "text-gray-900"  },
          { label: "Активных", value: activeSources.length, color: "text-blue-600"  },
          { label: "OK",       value: okCount,              color: "text-green-600" },
          { label: "Кэш",      value: warnCount,            color: "text-yellow-600"},
          { label: "Ошибка",   value: errorCount,           color: "text-red-600"   },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-xs text-gray-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Cards grid */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">Загрузка...</div>
      ) : sources.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          Источников нет. Нажмите «+ Добавить».
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {sources.map(source => (
            <SourceCard
              key={source.id}
              source={source}
              onEdit={s => { setEditSource(s); setShowForm(true); }}
              onDelete={handleDelete}
              onDiagnostics={setDiagSource}
              onTest={handleTest}
              onRawTags={handleRawTags}
            />
          ))}
        </div>
      )}

      {/* Raw tags loading overlay */}
      {rawTagsLoading && (
        <div className="fixed inset-0 bg-black bg-opacity-20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl px-8 py-6 text-center shadow-xl">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto mb-3" />
            <p className="text-sm text-gray-600">Загрузка XML-тегов...</p>
          </div>
        </div>
      )}

      {/* Test loading overlay */}
      {testLoading && (
        <div className="fixed inset-0 bg-black bg-opacity-20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl px-8 py-6 text-center shadow-xl">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3" />
            <p className="text-sm text-gray-600">Тестовый парсинг...</p>
          </div>
        </div>
      )}

      {/* Modals */}
      {showForm && (
        <SourceForm
          source={editSource}
          onSave={() => { setShowForm(false); setEditSource(null); load(); }}
          onClose={() => { setShowForm(false); setEditSource(null); }}
        />
      )}
      {diagSource && (
        <DiagnosticsPanel
          sourceId={diagSource.id}
          onClose={() => setDiagSource(null)}
        />
      )}
      {testResult && (
        <TestResultModal result={testResult} onClose={() => setTestResult(null)} />
      )}
      {rawTagsResult && (
        <RawTagsModal result={rawTagsResult} onClose={() => setRawTagsResult(null)} />
      )}
    </div>
  );
}
