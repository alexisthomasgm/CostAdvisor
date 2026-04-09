import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function Suppliers() {
  const { activeTeamId } = useAuth();
  const navigate = useNavigate();
  const [suppliers, setSuppliers] = useState([]);
  const [portfolio, setPortfolio] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [country, setCountry] = useState('');
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  const fetchData = () => {
    if (!activeTeamId) return;
    setLoading(true);
    Promise.all([
      api.get('/api/suppliers', { params: { team_id: activeTeamId } }),
      api.get('/api/portfolio/summary', { params: { team_id: activeTeamId } }),
    ])
      .then(([sRes, pRes]) => {
        setSuppliers(sRes.data);
        setPortfolio(pRes.data.models || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(fetchData, [activeTeamId]);

  const handleCreate = () => {
    if (!name.trim()) return;
    setSaving(true);
    api.post(`/api/suppliers?team_id=${activeTeamId}`, { name: name.trim(), country: country.trim() || null })
      .then(() => { setName(''); setCountry(''); setShowForm(false); fetchData(); })
      .catch(console.error)
      .finally(() => setSaving(false));
  };

  const handleDelete = (id) => {
    if (!confirm('Delete this supplier?')) return;
    api.delete(`/api/suppliers/${id}`)
      .then(fetchData)
      .catch(console.error);
  };

  const handleExportExcel = (id, name) => {
    api.get(`/api/suppliers/${id}/export-excel`, { responseType: 'blob' })
      .then(res => {
        const url = URL.createObjectURL(res.data);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${name.replace(/ /g, '_')}_Cost_Models.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch(console.error);
  };

  const getSupplierModels = (supplierId) =>
    portfolio.filter(m => m.supplier_name === suppliers.find(s => s.id === supplierId)?.name);

  return (
    <div className="ca-page ca-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div className="ca-h1">Suppliers</div>
        <button className="ca-btn ca-btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : '+ Add Supplier'}
        </button>
      </div>
      <p className="ca-subtitle">Manage suppliers for your team.</p>

      {showForm && (
        <div className="ca-card" style={{ marginBottom: 16 }}>
          <div className="ca-card-title">New Supplier</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 12, alignItems: 'flex-end' }}>
            <div>
              <label className="ca-label">Name *</label>
              <input className="ca-input" value={name} onChange={e => setName(e.target.value)} placeholder="Supplier name" />
            </div>
            <div>
              <label className="ca-label">Country</label>
              <input className="ca-input" value={country} onChange={e => setCountry(e.target.value)} placeholder="e.g. Germany" />
            </div>
            <button className="ca-btn ca-btn-primary" onClick={handleCreate} disabled={saving || !name.trim()}>
              {saving ? 'Saving...' : 'Create'}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ padding: 20, color: 'var(--muted)' }}>Loading...</div>
      ) : suppliers.length === 0 ? (
        <div className="ca-card" style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ color: 'var(--text-secondary)' }}>No suppliers yet.</div>
        </div>
      ) : (
        <div className="ca-card">
          <table className="ca-table">
            <thead>
              <tr>
                <th style={{ width: 30 }}></th>
                <th>Name</th>
                <th>Country</th>
                <th className="center">Products</th>
                <th className="center">Created</th>
                <th className="center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map(s => {
                const models = getSupplierModels(s.id);
                const isExpanded = expandedId === s.id;
                return (
                  <>
                    <tr key={s.id} style={{ cursor: models.length > 0 ? 'pointer' : 'default' }}
                      onClick={() => models.length > 0 && setExpandedId(isExpanded ? null : s.id)}>
                      <td style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'center' }}>
                        {models.length > 0 ? (isExpanded ? '\u25BC' : '\u25B6') : ''}
                      </td>
                      <td style={{ fontWeight: 600 }}>{s.name}</td>
                      <td style={{ color: 'var(--muted)' }}>{s.country || '\u2014'}</td>
                      <td className="center" style={{ fontSize: 11 }}>
                        <span style={{
                          padding: '1px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                          background: models.length > 0 ? 'rgba(79,255,176,.12)' : 'transparent',
                          color: models.length > 0 ? 'var(--accent)' : 'var(--muted)',
                        }}>
                          {models.length}
                        </span>
                      </td>
                      <td className="center" style={{ fontSize: 11, color: 'var(--muted)' }}>
                        {s.created_at ? new Date(s.created_at).toLocaleDateString() : '\u2014'}
                      </td>
                      <td className="center">
                        <button className="ca-btn ca-btn-ghost ca-btn-sm"
                          onClick={e => { e.stopPropagation(); navigate(`/suppliers/${s.id}/purchases`); }}>
                          Purchases
                        </button>
                        {models.length > 0 && (
                          <button className="ca-btn ca-btn-ghost ca-btn-sm" style={{ marginLeft: 4 }}
                            onClick={e => { e.stopPropagation(); handleExportExcel(s.id, s.name); }}>
                            Export
                          </button>
                        )}
                        <button className="ca-btn ca-btn-ghost ca-btn-sm" style={{ marginLeft: 4, color: 'var(--accent2)' }}
                          onClick={e => { e.stopPropagation(); handleDelete(s.id); }}>Delete</button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${s.id}-products`}>
                        <td colSpan={6} style={{ padding: '0 0 0 40px', background: 'var(--surface2)' }}>
                          <table className="ca-table" style={{ margin: '8px 0' }}>
                            <thead>
                              <tr>
                                <th>Family</th>
                                <th>Reference</th>
                                <th>Region</th>
                                <th className="center">Gap %</th>
                                <th className="center">Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {models.map(m => (
                                <tr key={m.cost_model_id}>
                                  <td style={{ fontWeight: 500 }}>{m.product_name}</td>
                                  <td style={{ color: 'var(--text-secondary)' }}>{m.product_reference || '\u2014'}</td>
                                  <td style={{ color: 'var(--muted)' }}>{m.region}</td>
                                  <td className="center">
                                    {m.gap_pct !== null ? (
                                      <span style={{
                                        padding: '1px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                                        color: m.gap_pct > 0 ? 'var(--accent2)' : m.gap_pct < 0 ? 'var(--accent)' : 'var(--muted)',
                                      }}>
                                        {m.gap_pct > 0 ? '+' : ''}{m.gap_pct.toFixed(1)}%
                                      </span>
                                    ) : (
                                      <span style={{ color: 'var(--muted)', fontSize: 11 }}>{'\u2014'}</span>
                                    )}
                                  </td>
                                  <td className="center">
                                    <button className="ca-btn ca-btn-ghost ca-btn-sm"
                                      onClick={e => { e.stopPropagation(); navigate(`/cost-models/${m.cost_model_id}`); }}>
                                      Edit
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
