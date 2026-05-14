/**
 * JK Management page — JK synonyms + JK coordinates in one place.
 *
 * JK Synonyms: map raw parser names → canonical name (e.g. "жк дк 17 этажей" → "ЖК Дом Культуры")
 * JK Coordinates: store precise lat/lon per canonical JK name to fill gaps in feeds
 * Missing Coords: list of active JKs that have no coordinates yet, with inline form
 */

import { useState, useEffect, useCallback } from "react";
import { Plus, Trash2, MapPin, Tag, AlertTriangle, Check, RefreshCw } from "lucide-react";
import api from "../api";

// ── Shared coord validator ────────────────────────────────────────────────────

function validateCoords(lat, lon) {
  const la = parseFloat(String(lat).replace(",", "."));
  const lo = parseFloat(String(lon).replace(",", "."));
  if (isNaN(la) || isNaN(lo)) return "Широта и долгота должны быть числами";
  if (la < 40 || la > 75)    return "Широта вне диапазона 40–75 (Россия)";
  if (lo < 20 || lo > 180)   return "Долгота вне диапазона 20–180 (Россия)";
  return null;
}

// ── JK Synonyms section ───────────────────────────────────────────────────────

function JkSynonymsSection() {
  const [synonyms, setSynonyms] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [rawName, setRawName]   = useState("");
  const [normName, setNormName] = useState("");
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api.get("/api/sources/synonyms/list")
      .then(r => setSynonyms(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    const r = rawName.trim();
    const n = normName.trim();
    if (!r || !n) { setError("Оба поля обязательны"); return; }
    setSaving(true); setError("");
    try {
      await api.post("/api/sources/synonyms/add", { raw_name: r, normalized_name: n });
      setRawName(""); setNormName("");
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "Ошибка сохранения");
    } finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    if (!confirm("Удалить синоним?")) return;
    await api.delete(`/api/sources/synonyms/${id}`);
    load();
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <div className="flex items-center gap-2 mb-4">
        <Tag size={18} className="text-blue-500" />
        <h2 className="text-base font-semibold text-gray-800">ЖК — синонимы</h2>
        <span className="ml-auto text-xs text-gray-400">{synonyms.length} записей</span>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        Если фид содержит нестандартное название ЖК, укажите здесь соответствие.
        При нормализации «Сырое название» будет заменено на «Каноническое».
      </p>

      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Сырое название (из фида)</label>
          <input
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="жк дк 17 этажей"
            value={rawName}
            onChange={e => setRawName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleAdd()}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Каноническое название</label>
          <input
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="ЖК Дом Культуры"
            value={normName}
            onChange={e => setNormName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleAdd()}
          />
        </div>
        <button
          onClick={handleAdd}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
        >
          <Plus size={14} /> Добавить
        </button>
      </div>

      {error && <p className="text-xs text-red-500 mb-3">{error}</p>}

      <div className="overflow-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="p-3 text-left">Сырое название</th>
              <th className="p-3 text-left">→</th>
              <th className="p-3 text-left">Каноническое название</th>
              <th className="p-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {synonyms.map(s => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="p-3 font-mono text-xs text-gray-700">{s.raw_name}</td>
                <td className="p-3 text-gray-400">→</td>
                <td className="p-3 font-medium text-gray-900">{s.normalized_name}</td>
                <td className="p-3 text-right">
                  <button onClick={() => handleDelete(s.id)} className="p-1.5 hover:bg-red-50 rounded-lg transition">
                    <Trash2 size={14} className="text-red-400" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-4 text-center text-gray-400 text-sm">Загрузка...</div>}
        {!loading && synonyms.length === 0 && <div className="p-4 text-center text-gray-400 text-sm">Синонимов нет</div>}
      </div>
    </div>
  );
}

// ── Missing coordinates section ───────────────────────────────────────────────

function MissingCoordsSection({ onSaved }) {
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(true);
  // inline edit state: { [jk_name]: { lat, lon, saving, error } }
  const [inline, setInline]   = useState({});

  const load = useCallback(() => {
    setLoading(true);
    api.get("/api/admin/jk-coordinates/missing")
      .then(r => setRows(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const setField = (name, field, value) =>
    setInline(prev => ({ ...prev, [name]: { lat: "", lon: "", saving: false, error: "", ...prev[name], [field]: value } }));

  const handleSave = async (jk_name) => {
    const st = inline[jk_name] || {};
    const err = validateCoords(st.lat, st.lon);
    if (err) { setField(jk_name, "error", err); return; }
    setField(jk_name, "saving", true);
    setField(jk_name, "error", "");
    try {
      await api.post("/api/admin/jk-coordinates", {
        jk_name,
        latitude:  parseFloat(String(st.lat).replace(",", ".")),
        longitude: parseFloat(String(st.lon).replace(",", ".")),
      });
      // Remove from inline state and reload both lists
      setInline(prev => { const n = { ...prev }; delete n[jk_name]; return n; });
      load();
      if (onSaved) onSaved();  // refresh coordinates table above
    } catch (e) {
      setField(jk_name, "error", e.response?.data?.detail || "Ошибка");
    } finally {
      setField(jk_name, "saving", false);
    }
  };

  if (!loading && rows.length === 0) return null;  // hide section when all covered

  return (
    <div className="bg-white rounded-xl border border-orange-200 shadow-sm p-5">
      <div className="flex items-center gap-2 mb-1">
        <AlertTriangle size={18} className="text-orange-500" />
        <h2 className="text-base font-semibold text-gray-800">ЖК без координат</h2>
        {!loading && (
          <span className="ml-1 px-2 py-0.5 text-xs font-semibold bg-orange-100 text-orange-700 rounded-full">
            {rows.length}
          </span>
        )}
        <button onClick={load} className="ml-auto p-1.5 hover:bg-gray-100 rounded-lg transition" title="Обновить">
          <RefreshCw size={14} className="text-gray-400" />
        </button>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        Активные ЖК, у которых ни один объект не имеет координат в базе.
        Введите широту и долготу прямо в строке — данные сохранятся и применятся при следующей синхронизации.
      </p>

      <div className="overflow-auto rounded-lg border border-orange-100">
        <table className="w-full text-sm">
          <thead className="bg-orange-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="p-3 text-left">ЖК</th>
              <th className="p-3 text-right">Объектов</th>
              <th className="p-3 text-left">Пример адреса</th>
              <th className="p-3 text-center w-32">Широта</th>
              <th className="p-3 text-center w-32">Долгота</th>
              <th className="p-3 w-24" />
            </tr>
          </thead>
          <tbody className="divide-y divide-orange-50">
            {rows.map(row => {
              const st = inline[row.jk_name] || { lat: "", lon: "" };
              const ready = st.lat && st.lon;
              return (
                <tr key={row.jk_name} className="hover:bg-orange-50/40">
                  <td className="p-3 font-medium text-gray-900">{row.jk_name}</td>
                  <td className="p-3 text-right tabular-nums text-gray-600">{row.object_count}</td>
                  <td className="p-3 text-xs text-gray-400 max-w-[220px] truncate">{row.sample_address || "—"}</td>
                  <td className="p-2">
                    <input
                      className="w-full border border-gray-200 rounded px-2 py-1.5 text-xs text-center focus:outline-none focus:ring-2 focus:ring-orange-300"
                      placeholder="53.347891"
                      value={st.lat}
                      onChange={e => setField(row.jk_name, "lat", e.target.value)}
                      onKeyDown={e => e.key === "Enter" && ready && handleSave(row.jk_name)}
                    />
                  </td>
                  <td className="p-2">
                    <input
                      className="w-full border border-gray-200 rounded px-2 py-1.5 text-xs text-center focus:outline-none focus:ring-2 focus:ring-orange-300"
                      placeholder="83.776543"
                      value={st.lon}
                      onChange={e => setField(row.jk_name, "lon", e.target.value)}
                      onKeyDown={e => e.key === "Enter" && ready && handleSave(row.jk_name)}
                    />
                  </td>
                  <td className="p-2 text-center">
                    {st.error && (
                      <p className="text-xs text-red-500 mb-1 leading-tight">{st.error}</p>
                    )}
                    <button
                      onClick={() => handleSave(row.jk_name)}
                      disabled={!ready || st.saving}
                      className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition mx-auto
                        ${ready && !st.saving
                          ? "bg-green-600 text-white hover:bg-green-700"
                          : "bg-gray-100 text-gray-400 cursor-not-allowed"}`}
                    >
                      <Check size={12} />
                      {st.saving ? "..." : "Сохранить"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {loading && <div className="p-4 text-center text-gray-400 text-sm">Загрузка...</div>}
      </div>
    </div>
  );
}

// ── JK Coordinates section ────────────────────────────────────────────────────

function JkCoordinatesSection({ reloadSignal }) {
  const [coords, setCoords]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [jkName, setJkName]     = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api.get("/api/admin/jk-coordinates")
      .then(r => setCoords(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load, reloadSignal]);

  const handleAdd = async () => {
    const name = jkName.trim();
    const err = validateCoords(latitude, longitude);
    if (!name) { setError("Название ЖК обязательно"); return; }
    if (err)   { setError(err); return; }
    setSaving(true); setError("");
    try {
      await api.post("/api/admin/jk-coordinates", {
        jk_name: name,
        latitude:  parseFloat(String(latitude).replace(",", ".")),
        longitude: parseFloat(String(longitude).replace(",", ".")),
      });
      setJkName(""); setLatitude(""); setLongitude("");
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "Ошибка сохранения");
    } finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    if (!confirm("Удалить координаты ЖК?")) return;
    await api.delete(`/api/admin/jk-coordinates/${id}`);
    load();
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <div className="flex items-center gap-2 mb-4">
        <MapPin size={18} className="text-green-500" />
        <h2 className="text-base font-semibold text-gray-800">ЖК — координаты</h2>
        <span className="ml-auto text-xs text-gray-400">{coords.length} записей</span>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        Если фид не содержит координат ЖК (или указывает адрес офиса продаж),
        введите точные координаты вручную. При синхронизации они будут подставлены
        автоматически в поля Latitude/Longitude.
      </p>

      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Каноническое название ЖК</label>
          <input
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-green-300"
            placeholder="ЖК Широта"
            value={jkName}
            onChange={e => setJkName(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Широта</label>
          <input
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-green-300"
            placeholder="53.347891"
            value={latitude}
            onChange={e => setLatitude(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Долгота</label>
          <input
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-green-300"
            placeholder="83.776543"
            value={longitude}
            onChange={e => setLongitude(e.target.value)}
          />
        </div>
        <button
          onClick={handleAdd}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium disabled:opacity-50"
        >
          <Plus size={14} /> Сохранить
        </button>
      </div>

      {error && <p className="text-xs text-red-500 mb-3">{error}</p>}

      <div className="overflow-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="p-3 text-left">ЖК</th>
              <th className="p-3 text-right">Широта</th>
              <th className="p-3 text-right">Долгота</th>
              <th className="p-3 text-right">Обновлено</th>
              <th className="p-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {coords.map(c => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="p-3 font-medium text-gray-900">{c.jk_name}</td>
                <td className="p-3 text-right font-mono text-xs text-gray-700">{c.latitude}</td>
                <td className="p-3 text-right font-mono text-xs text-gray-700">{c.longitude}</td>
                <td className="p-3 text-right text-xs text-gray-400">
                  {c.updated_at ? new Date(c.updated_at).toLocaleDateString("ru-RU") : "—"}
                </td>
                <td className="p-3 text-right">
                  <button onClick={() => handleDelete(c.id)} className="p-1.5 hover:bg-red-50 rounded-lg transition">
                    <Trash2 size={14} className="text-red-400" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-4 text-center text-gray-400 text-sm">Загрузка...</div>}
        {!loading && coords.length === 0 && <div className="p-4 text-center text-gray-400 text-sm">Координат нет</div>}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function JkManagement() {
  // When MissingCoordsSection saves a row → signal JkCoordinatesSection to reload
  const [coordReload, setCoordReload] = useState(0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Управление ЖК</h1>
        <p className="text-gray-500 text-sm mt-0.5">
          Синонимы унифицируют названия ЖК из разных источников. Координаты заполняют
          поля широты/долготы, если фид их не предоставляет.
        </p>
      </div>

      {/* Orange alert block — only shows when there are JKs without coords */}
      <MissingCoordsSection onSaved={() => setCoordReload(n => n + 1)} />

      <JkSynonymsSection />
      <JkCoordinatesSection reloadSignal={coordReload} />
    </div>
  );
}
