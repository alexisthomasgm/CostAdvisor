import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { qLabel, QUARTER_OPTS } from '../utils/quarters';

export default function Pricing() {
  const { costModelId } = useParams();
  const navigate = useNavigate();

  // Pricing history
  const [prices, setPrices] = useState([]);
  const [volumes, setVolumes] = useState([]);
  const [loadingPrices, setLoadingPrices] = useState(true);

  // Inline add form
  const [addYear, setAddYear] = useState(2025);
  const [addQuarter, setAddQuarter] = useState(1);
  const [addPrice, setAddPrice] = useState('');
  const [addVolume, setAddVolume] = useState('');
  const [saving, setSaving] = useState(false);

  // Editing state
  const [editKey, setEditKey] = useState(null); // "year-quarter"
  const [editPrice, setEditPrice] = useState('');
  const [editVolume, setEditVolume] = useState('');

  // Price change analyzer
  const [fromYear, setFromYear] = useState(2024);
  const [fromQuarter, setFromQuarter] = useState(1);
  const [toYear, setToYear] = useState(2025);
  const [toQuarter, setToQuarter] = useState(1);
  const [analysis, setAnalysis] = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);


  // Model metadata
  const [model, setModel] = useState(null);

  useEffect(() => {
    if (!costModelId) return;
    api.get(`/api/cost-models/${costModelId}`).then(({ data }) => setModel(data));
    fetchData();
  }, [costModelId]);

  const fetchData = () => {
    setLoadingPrices(true);
    Promise.all([
      api.get(`/api/prices/${costModelId}`),
      api.get(`/api/volumes/${costModelId}`),
    ])
      .then(([pRes, vRes]) => { setPrices(pRes.data); setVolumes(vRes.data); })
      .finally(() => setLoadingPrices(false));
  };

  const addPriceRow = () => {
    if (!addPrice && !addVolume) return;
    setSaving(true);
    const promises = [];
    if (addPrice) {
      const body = { year: addYear, quarter: addQuarter, price: parseFloat(addPrice) };
      promises.push(api.put(`/api/prices/${costModelId}/${addYear}/${addQuarter}`, body));
    }
    if (addVolume) {
      promises.push(api.put(`/api/volumes/${costModelId}/${addYear}/${addQuarter}`, {
        year: addYear, quarter: addQuarter, volume: parseFloat(addVolume),
      }));
    }
    Promise.all(promises)
      .then(() => { setAddPrice(''); setAddVolume(''); fetchData(); })
      .finally(() => setSaving(false));
  };

  const startEdit = (row) => {
    setEditKey(`${row.year}-${row.quarter}`);
    setEditPrice(row.price != null ? String(row.price) : '');
    setEditVolume(row.volume != null ? String(row.volume) : '');
  };

  const saveEdit = (row) => {
    const promises = [];
    if (editPrice !== '') {
      const body = { year: row.year, quarter: row.quarter, price: parseFloat(editPrice) };
      promises.push(api.put(`/api/prices/${costModelId}/${row.year}/${row.quarter}`, body));
    }
    if (editVolume !== '') {
      promises.push(api.put(`/api/volumes/${costModelId}/${row.year}/${row.quarter}`, {
        year: row.year, quarter: row.quarter, volume: parseFloat(editVolume),
      }));
    }
    Promise.all(promises).then(() => { setEditKey(null); fetchData(); });
  };

  const deleteRow = (row) => {
    const promises = [];
    if (row.price != null) {
      promises.push(api.delete(`/api/prices/${costModelId}/${row.year}/${row.quarter}`).catch(() => {}));
    }
    if (row.volume != null) {
      promises.push(api.delete(`/api/volumes/${costModelId}/${row.year}/${row.quarter}`).catch(() => {}));
    }
    Promise.all(promises).then(() => fetchData());
  };

  const runAnalysis = () => {
    setLoadingAnalysis(true);
    api.post('/api/costing/price-change', {
      cost_model_id: costModelId,
      from_year: fromYear,
      from_quarter: fromQuarter,
      to_year: toYear,
      to_quarter: toQuarter,
    })
      .then(({ data }) => setAnalysis(data))
      .finally(() => setLoadingAnalysis(false));
  };

  // Upload handler
  const handleUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    api.post(`/api/prices/${costModelId}/upload`, formData)
      .then(() => fetchData());
    e.target.value = '';
  };

  const sym = model?.currency === 'EUR' ? '\u20AC' : '$';

  // Merge prices and volumes into unified rows keyed by year-quarter
  const mergedRows = (() => {
    const map = {};
    prices.forEach(p => {
      const key = `${p.year}-${p.quarter}`;
      map[key] = { year: p.year, quarter: p.quarter, price: p.price };
    });
    volumes.forEach(v => {
      const key = `${v.year}-${v.quarter}`;
      if (map[key]) {
        map[key].volume = v.volume;
        map[key].unit = v.unit;
      } else {
        map[key] = { year: v.year, quarter: v.quarter, volume: v.volume, unit: v.unit };
      }
    });
    return Object.values(map).sort((a, b) => a.year - b.year || a.quarter - b.quarter);
  })();

  return (
    <div className="ca-page ca-fade-in">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div className="ca-h1">Pricing</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}`)}>View Model</button>
          <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}/evolution`)}>Evolution</button>
          <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}/brief`)}>Brief</button>
        </div>
      </div>
      {model && (
        <p className="ca-subtitle">
          {model.product_name}{model.supplier_name ? ` \u00B7 ${model.supplier_name}` : ''} \u00B7 {model.region} \u00B7 {model.currency}
        </p>
      )}

      {/* Two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>
        {/* LEFT: Pricing History */}
        <div>
          <div className="ca-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div className="ca-card-title" style={{ margin: 0 }}>Pricing & Volume History</div>
              <label className="ca-btn ca-btn-ghost ca-btn-sm" style={{ cursor: 'pointer' }}>
                Upload CSV/Excel
                <input type="file" accept=".csv,.xlsx" onChange={handleUpload} style={{ display: 'none' }} />
              </label>
            </div>

            {loadingPrices ? (
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>Loading...</div>
            ) : mergedRows.length === 0 ? (
              <div style={{ color: 'var(--muted)', fontSize: 12, padding: '16px 0' }}>
                No data yet. Add prices and quantities below or upload a file.
              </div>
            ) : (
              <div className="ca-scroll-x">
                <table className="ca-table">
                  <thead>
                    <tr>
                      <th>Period</th>
                      <th className="center">Price</th>
                      <th className="center">Quantity</th>
                      <th className="center" style={{ width: 100 }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mergedRows.map(row => {
                      const key = `${row.year}-${row.quarter}`;
                      const isEditing = editKey === key;
                      return (
                        <tr key={key}>
                          <td>{qLabel(row.year, row.quarter)}</td>
                          <td className="center">
                            {isEditing ? (
                              <input
                                type="number"
                                step="0.01"
                                className="ca-input"
                                style={{ width: 100, textAlign: 'center', fontSize: 12, padding: '3px 6px' }}
                                value={editPrice}
                                onChange={e => setEditPrice(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && saveEdit(row)}
                                autoFocus
                              />
                            ) : (
                              <span style={{ fontWeight: 500 }}>
                                {row.price != null ? `${sym}${row.price.toFixed(4)}` : '\u2014'}
                              </span>
                            )}
                          </td>
                          <td className="center">
                            {isEditing ? (
                              <input
                                type="number"
                                step="1"
                                className="ca-input"
                                style={{ width: 100, textAlign: 'center', fontSize: 12, padding: '3px 6px' }}
                                value={editVolume}
                                onChange={e => setEditVolume(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && saveEdit(row)}
                              />
                            ) : (
                              <span style={{ fontWeight: 500 }}>
                                {row.volume != null ? `${Number(row.volume).toLocaleString()} ${row.unit || 'kg'}` : '\u2014'}
                              </span>
                            )}
                          </td>
                          <td className="center">
                            {isEditing ? (
                              <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                                <button className="ca-btn ca-btn-sm" onClick={() => saveEdit(row)}>Save</button>
                                <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={() => setEditKey(null)}>Cancel</button>
                              </div>
                            ) : (
                              <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                                <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={() => startEdit(row)}>Edit</button>
                                <button
                                  className="ca-btn ca-btn-ghost ca-btn-sm"
                                  style={{ color: 'var(--accent2)' }}
                                  onClick={() => deleteRow(row)}
                                >Del</button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Inline add row */}
            <div style={{ marginTop: 12, padding: '12px 0', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, alignItems: 'center' }}>
              <select
                className="ca-select"
                style={{ width: 90, fontSize: 11, padding: '4px 8px' }}
                value={`${addYear}-${addQuarter}`}
                onChange={e => {
                  const [y, q] = e.target.value.split('-').map(Number);
                  setAddYear(y); setAddQuarter(q);
                }}
              >
                {QUARTER_OPTS.map(o => (
                  <option key={o.label} value={`${o.year}-${o.quarter}`}>{o.label}</option>
                ))}
              </select>
              <input
                type="number"
                step="0.01"
                className="ca-input"
                style={{ width: 100, fontSize: 12, padding: '4px 8px' }}
                placeholder="Price"
                value={addPrice}
                onChange={e => setAddPrice(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addPriceRow()}
              />
              <input
                type="number"
                step="1"
                className="ca-input"
                style={{ width: 100, fontSize: 12, padding: '4px 8px' }}
                placeholder="Quantity"
                value={addVolume}
                onChange={e => setAddVolume(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addPriceRow()}
              />
              <button className="ca-btn ca-btn-sm" onClick={addPriceRow} disabled={saving || (!addPrice && !addVolume)}>
                Add
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT: Price Change Analyzer */}
        <div>
          <div className="ca-card">
            <div className="ca-card-title" style={{ marginBottom: 12 }}>Price Change Analyzer</div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 14 }}>
              <select
                className="ca-select"
                style={{ width: 90, fontSize: 11, padding: '4px 8px' }}
                value={`${fromYear}-${fromQuarter}`}
                onChange={e => {
                  const [y, q] = e.target.value.split('-').map(Number);
                  setFromYear(y); setFromQuarter(q);
                }}
              >
                {QUARTER_OPTS.map(o => (
                  <option key={o.label} value={`${o.year}-${o.quarter}`}>{o.label}</option>
                ))}
              </select>
              <span style={{ fontSize: 10, color: 'var(--muted)' }}>to</span>
              <select
                className="ca-select"
                style={{ width: 90, fontSize: 11, padding: '4px 8px' }}
                value={`${toYear}-${toQuarter}`}
                onChange={e => {
                  const [y, q] = e.target.value.split('-').map(Number);
                  setToYear(y); setToQuarter(q);
                }}
              >
                {QUARTER_OPTS.map(o => (
                  <option key={o.label} value={`${o.year}-${o.quarter}`}>{o.label}</option>
                ))}
              </select>
              <button className="ca-btn ca-btn-sm" onClick={runAnalysis} disabled={loadingAnalysis}>
                {loadingAnalysis ? 'Analyzing...' : 'Analyze'}
              </button>
            </div>

            {analysis && (
              <>
                {/* Summary metric */}
                <div className="ca-metric" style={{ marginBottom: 16 }}>
                  <div className="ca-metric-lbl">Should-Cost Change</div>
                  <div className="ca-metric-val" style={{ color: analysis.fair_change_pct > 0 ? 'var(--accent2)' : 'var(--accent)' }}>
                    {analysis.fair_change_pct > 0 ? '+' : ''}{analysis.fair_change_pct.toFixed(2)}%
                  </div>
                </div>

                {/* Component breakdown table */}
                <div className="ca-scroll-x">
                  <table className="ca-table">
                    <thead>
                      <tr>
                        <th>Component</th>
                        <th className="center">Weight</th>
                        <th className="center">Index ({analysis.from_label})</th>
                        <th className="center">Index ({analysis.to_label})</th>
                        <th className="center">Index Change</th>
                        <th className="center">Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis.components.map(c => (
                        <tr key={c.label}>
                          <td>{c.label}</td>
                          <td className="center">{c.weight.toFixed(1)}%</td>
                          <td className="center" style={{ fontSize: 11 }}>{c.index_start?.toFixed(2) ?? '\u2014'}</td>
                          <td className="center" style={{ fontSize: 11 }}>{c.index_end?.toFixed(2) ?? '\u2014'}</td>
                          <td className="center" style={{ color: c.index_change_pct > 0 ? 'var(--accent2)' : c.index_change_pct < 0 ? 'var(--accent)' : 'var(--muted)' }}>
                            {c.index_change_pct > 0 ? '+' : ''}{c.index_change_pct.toFixed(1)}%
                          </td>
                          <td className="center" style={{ fontWeight: 500, color: c.contribution_pct > 0 ? 'var(--accent2)' : c.contribution_pct < 0 ? 'var(--accent)' : 'var(--muted)' }}>
                            {c.contribution_pct > 0 ? '+' : ''}{c.contribution_pct.toFixed(2)}%
                          </td>
                        </tr>
                      ))}
                      {/* Margin row */}
                      {analysis.margin_weight > 0 && (
                        <tr style={{ opacity: 0.6 }}>
                          <td>Margin</td>
                          <td className="center">{analysis.margin_weight.toFixed(1)}%</td>
                          <td className="center">\u2014</td>
                          <td className="center">\u2014</td>
                          <td className="center" style={{ color: 'var(--muted)' }}>0.0%</td>
                          <td className="center" style={{ color: 'var(--muted)' }}>0.00%</td>
                        </tr>
                      )}
                      {/* Total row */}
                      <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 600 }}>
                        <td>Total</td>
                        <td className="center">100%</td>
                        <td></td>
                        <td></td>
                        <td></td>
                        <td className="center" style={{ color: analysis.fair_change_pct > 0 ? 'var(--accent2)' : 'var(--accent)' }}>
                          {analysis.fair_change_pct > 0 ? '+' : ''}{analysis.fair_change_pct.toFixed(2)}%
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {!analysis && !loadingAnalysis && (
              <div style={{ color: 'var(--muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
                Select a period range and click Analyze to see what a fair price change should be based on index movements.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
