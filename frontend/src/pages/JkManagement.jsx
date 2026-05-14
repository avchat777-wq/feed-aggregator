/**
 * JK Management page — JK synonyms + JK coordinates in one place.
 *
 * JK Synonyms: map raw parser names → canonical name (e.g. "жк дк 17 этажей" → "ЖК Дом Культуры")
 * JK Coordinates: store precise lat/lon per canonical JK name to fill gaps in feeds
 */

import { useState, useEffect } from "react";
import { Plus, Trash2, MapPin, Tag } from "lucide-react";
import api from "../api";

// ── JK Synonyms section ───────────────────────────────────────────────────────

function JkSynonymsSection() {
  const [synonyms, setSynonyms]     = useState([]);
  const [loading, setLoading]       = useState(true);
  const [rawName, setRawName]       = useState("");
  const [normName, setNormName]     = useState("");
  const [saving, setSaving]         = useState(false);
  const [error, setError]           = useState("");

  const load = () => {
    setLoading(true);
    api.get("/api/sources/synonyms/list")
      .then(r => setSynonyms(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    const r = rawName.trim();
    const n = normName.trim();
    if (!r || !n) { setError("Оба поля обязательны"); return; }
    setSaving(true);
    setError("");
    try {
      await api.post("/api/sources/synonyms/add", { raw_name: r, normalized_name: n });
      setRawName("");
      setNormName("");
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
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

      {/* Add form */}
      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Сырое название (из фида)
          </label>
          <input
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="жк дк 17 этажей"
            value={rawName}
            onChange={e => setRawName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleAdd()}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Каноническое название
          </label>
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
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {synonyms.map(s => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="p-3 font-mono text-xs text-gray-700">{s.raw_name}</td>
                <td className="p-3 text-gray-400">→</td>
                <td className="p-3 font-medium text-gray-900">{s.normalized_name}</td>
                <td className="p-3 text-right">
                  <button
                    onClick={() => handleDelete(s.id)}
                    className="p-1.5 hover:bg-red-50 rounded-lg transition"
                  >
                    <Trash2 size={14} className="text-red-400" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-4 text-center text-gray-400 text-sm">Загрузка...</div>}
        {!loading && synonyms.length === 0 && (
          <div className="p-4 text-center text-gray-400 text-sm">Синонимов нет</div>
        )}
      </div>
    </div>
  );
}

// ── JK Coordinates section ────────────────────────────────────────────────────

function JkCoordinatesSection() {
  const [coords, setCoords]         = useState([]);
  const [loading, setLoading]       = useState(true);
  const [jkName, setJkName]         = useState("");
  const [latitude, setLatitude]     = useState("");
  const [longitude, setLongitude]   = useState("");
  const [saving, setSaving]         = useState(false);
  const [error, setError]           = useState("");

  const load = () => {
    setLoading(true);
    api.get("/api/admin/jk-coordinates")
      .then(r => setCoords(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    const name = jkName.trim();
    const lat  = parseFloat(latitude.replace(",", "."));
    const lon  = parseFloat(longitude.replace(",", "."));

    if (!name)              { setError("Название ЖК обязательно"); return; }
    if (isNaN(lat) || isNaN(lon)) { setError("Широта и долгота должны быть числами"); return; }
    if (lat < 40 || lat > 75)    { setError("Широта должна быть в диапазоне 40–75 (Россия)"); return; }
    if (lon < 20 || lon > 180)   { setError("Долгота должна быть в диапазоне 20–180 (Россия)"); return; }

    setSaving(true);
    setError("");
    try {
      await api.post("/api/admin/jk-coordinates", {
        jk_name: name,
        latitude: lat,
        longitude: lon,
      });
      setJkName("");
      setLatitude("");
      setLongitude("");
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "Ошибка сохранения");
    } finally {
      setSaving(false);
    }
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

      {/* Add form */}
      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Каноническое название ЖК
          </label>
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
              <th className="p-3"></th>
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
                  <button
                    onClick={() => handleDelete(c.id)}
                    className="p-1.5 hover:bg-red-50 rounded-lg transition"
                  >
                    <Trash2 size={14} className="text-red-400" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-4 text-center text-gray-400 text-sm">Загрузка...</div>}
        {!loading && coords.length === 0 && (
          <div className="p-4 text-center text-gray-400 text-sm">Координат нет</div>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function JkManagement() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Управление ЖК</h1>
        <p className="text-gray-500 text-sm mt-0.5">
          Синонимы унифицируют названия ЖК из разных источников. Координаты заполняют
          поля широты/долготы, если фид их не предоставляет.
        </p>
      </div>

      <JkSynonymsSection />
      <JkCoordinatesSection />
    </div>
  );
}
