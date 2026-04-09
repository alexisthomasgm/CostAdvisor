import { useState, useEffect, useMemo, useRef } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';
import EditCellModal from '../components/EditCellModal';
import IndexDetailPanel from '../components/IndexDetailPanel';
import AddIndexModal from '../components/AddIndexModal';
import IndexPopupModal from '../components/IndexPopupModal';

export default function Indexes() {
  const { activeTeamId, user } = useAuth();
  const [data, setData] = useState([]);
  const [commodities, setCommodities] = useState([]);
  const [sources, setSources] = useState([]);
  const [filterOptions, setFilterOptions] = useState({ products: [], suppliers: [], regions: [], materials: [] });
  const [loading, setLoading] = useState(true);

  // Filters
  const [regionFilter, setRegionFilter] = useState('all');
  const [materialFilter, setMaterialFilter] = useState('all');
  const [productFilter, setProductFilter] = useState('all');
  const [supplierFilter, setSupplierFilter] = useState('all');
  const [startPeriod, setStartPeriod] = useState('2023-1');
  const [endPeriod, setEndPeriod] = useState('2026-1');

  // UI state
  const [editModal, setEditModal] = useState(null);
  const [expandedRow, setExpandedRow] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [popupRow, setPopupRow] = useState(null); // {commodity_id, mat, reg, cells, commodity}
  const [filtersOpen, setFiltersOpen] = useState(false);
  const tableScrollRef = useRef(null);

  const fetchData = async () => {
    if (!activeTeamId) return;
    setLoading(true);
    try {
      const params = { team_id: activeTeamId };

      // Add product/supplier filter params
      if (productFilter !== 'all') params.product_id = productFilter;
      if (supplierFilter !== 'all') params.supplier_id = supplierFilter;

      // Add time range params
      if (startPeriod) {
        const [sy, sq] = startPeriod.split('-');
        params.from_year = +sy;
        params.from_quarter = +sq;
      }
      if (endPeriod) {
        const [ey, eq] = endPeriod.split('-');
        params.to_year = +ey;
        params.to_quarter = +eq;
      }

      const [indexRes, commRes, srcRes] = await Promise.all([
        api.get('/api/indexes/values', { params }),
        api.get('/api/indexes'),
        api.get('/api/indexes/sources', { params: { team_id: activeTeamId } }),
      ]);
      setData(indexRes.data);
      setCommodities(commRes.data);
      setSources(srcRes.data);

      // Fetch filter options separately so failure doesn't block the page
      try {
        const filterRes = await api.get('/api/indexes/filter-options', { params: { team_id: activeTeamId } });
        setFilterOptions(filterRes.data);
      } catch {
        // Non-critical — filters just won't have product/supplier options
      }
    } catch (err) {
      console.error('Failed to fetch indexes:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [activeTeamId, productFilter, supplierFilter, startPeriod, endPeriod]);

  // Build commodity lookup map
  const commodityMap = useMemo(() => {
    const m = new Map();
    commodities.forEach(c => m.set(c.id, c));
    return m;
  }, [commodities]);

  // Dynamically compute available periods — sorted descending (most recent first)
  const periods = useMemo(() => {
    const periodSet = new Set();
    data.forEach(d => periodSet.add(`${d.year}-${d.quarter}`));
    return [...periodSet]
      .map(p => { const [y, q] = p.split('-'); return { year: +y, quarter: +q }; })
      .sort((a, b) => a.year - b.year || a.quarter - b.quarter)
      .map(p => ({ ...p, label: `Q${p.quarter}-${String(p.year).slice(2)}` }));
  }, [data]);

  // Auto-scroll table to the right so most recent periods are visible
  useEffect(() => {
    if (!loading && tableScrollRef.current) {
      const el = tableScrollRef.current;
      el.scrollLeft = el.scrollWidth;
    }
  }, [loading, periods.length]);

  // Generate period options for the time range selectors
  const periodOptions = useMemo(() => {
    const opts = [];
    for (let y = 2020; y <= 2027; y++) {
      for (let q = 1; q <= 4; q++) {
        opts.push({ value: `${y}-${q}`, label: `Q${q}-${String(y).slice(2)}` });
      }
    }
    return opts;
  }, []);

  const regions = useMemo(() => [...new Set(data.map(d => d.region))].sort(), [data]);
  const materialNames = useMemo(() => [...new Set(data.map(d => d.commodity_name))].sort(), [data]);

  // Reshape flat data into table rows
  const rows = useMemo(() => {
    const grouped = {};
    data.forEach(d => {
      const key = `${d.commodity_name}__${d.region}`;
      if (!grouped[key]) {
        grouped[key] = { mat: d.commodity_name, reg: d.region, commodity_id: d.commodity_id, valMap: {} };
      }
      const periodKey = `Q${d.quarter}-${String(d.year).slice(2)}`;
      grouped[key].valMap[periodKey] = d;
    });

    return Object.values(grouped)
      .filter(r => (regionFilter === 'all' || r.reg === regionFilter))
      .filter(r => (materialFilter === 'all' || r.mat === materialFilter))
      .map(r => {
        const cells = periods.map(p => r.valMap[p.label] || null);
        const values = cells.map(c => c?.value ?? null);
        const base = values[0]; // earliest period (left-most column)
        return { ...r, cells, values, base };
      });
  }, [data, regionFilter, materialFilter, periods]);

  const findSource = (commodity_id, region) =>
    sources.find(s => s.commodity_id === commodity_id && s.region === region) || null;

  const getGlobalScraperInfo = (commodity_id) => {
    const cell = data.find(d => d.commodity_id === commodity_id && d.global_scraper);
    if (!cell) return null;
    return { scraper: cell.global_scraper, scrape_at: cell.global_scrape_at };
  };

  const getHealthClass = (commodity_id, region) => {
    const src = findSource(commodity_id, region);
    if (src) {
      if (!src.last_scrape_at) return 'idx-health-none';
      if (src.last_scrape_status === 'error') return 'idx-health-error';
      const daysSince = (Date.now() - new Date(src.last_scrape_at).getTime()) / 86400000;
      if (daysSince > 30) return 'idx-health-stale';
      return 'idx-health-ok';
    }
    const gs = getGlobalScraperInfo(commodity_id);
    if (gs) {
      if (!gs.scrape_at) return 'idx-health-ok';
      const daysSince = (Date.now() - new Date(gs.scrape_at).getTime()) / 86400000;
      if (daysSince > 90) return 'idx-health-stale';
      return 'idx-health-ok';
    }
    return 'idx-health-none';
  };

  const getHealthTitle = (commodity_id, region) => {
    const src = findSource(commodity_id, region);
    if (src) {
      if (src.last_scrape_at) return `Team source: ${src.source_type} — last ${new Date(src.last_scrape_at).toLocaleDateString()}`;
      return `Team source: ${src.source_type}`;
    }
    const gs = getGlobalScraperInfo(commodity_id);
    if (gs) {
      const lastAt = gs.scrape_at ? ` — last ${new Date(gs.scrape_at).toLocaleDateString()}` : '';
      return `Auto-scraped (${gs.scraper})${lastAt}`;
    }
    return 'No source configured';
  };

  const handleCellClick = (cell) => {
    if (!cell) return;
    setEditModal(cell);
  };

  const handleEditSaved = (updatedCell) => {
    if (updatedCell) {
      setData(prev => prev.map(d =>
        d.commodity_id === updatedCell.commodity_id &&
        d.region === updatedCell.region &&
        d.year === updatedCell.year &&
        d.quarter === updatedCell.quarter
          ? updatedCell : d
      ));
    } else {
      fetchData();
    }
  };

  const handleSourceChanged = () => { fetchData(); };
  const handleRowRemoved = () => { setExpandedRow(null); setPopupRow(null); fetchData(); };

  const handleMaterialClick = (r) => {
    setPopupRow({
      commodity_id: r.commodity_id,
      mat: r.mat,
      reg: r.reg,
      cells: r.cells,
      commodity: commodityMap.get(r.commodity_id),
    });
  };

  const exportCsv = () => {
    const header = ['Material', 'Region', ...periods.map(p => p.label)].join(',');
    const csvRows = rows.map(r =>
      [r.mat, r.reg, ...r.values.map(v => v !== null ? v : '')].join(',')
    );
    const csv = [header, ...csvRows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'indexes.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="ca-page ca-fade-in">
      {/* Header with action buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="ca-h1">Market Indexes</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={exportCsv}>Export CSV</button>
          <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={() => setShowAddModal(true)}>+ Add Index</button>
        </div>
      </div>
      <p className="ca-subtitle">
        Quarterly commodity index values by material and region.
        <span style={{ color: 'var(--accent4)', fontSize: 10, marginLeft: 8 }}>
          Click a material name for details. Click a cell to edit.
        </span>
      </p>

      {/* Collapsible Filter Bar */}
      {(() => {
        const activeCount = [
          regionFilter !== 'all',
          productFilter !== 'all',
          supplierFilter !== 'all',
          materialFilter !== 'all',
          startPeriod !== '2023-1',
          endPeriod !== '2026-1',
        ].filter(Boolean).length;

        return (
          <div className="ca-card" style={{ marginBottom: 16, padding: 0 }}>
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              style={{
                width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 16px', background: 'none', border: 'none', color: 'var(--text)',
                cursor: 'pointer', fontSize: 12, fontFamily: 'inherit',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className={`idx-chevron${filtersOpen ? ' open' : ''}`} style={{ fontSize: 10 }}>&#9654;</span>
                <span style={{ fontWeight: 500 }}>Filters</span>
                {activeCount > 0 && (
                  <span className="ca-badge" style={{ background: 'var(--accent)', color: '#000', fontSize: 9 }}>
                    {activeCount} active
                  </span>
                )}
              </span>
              {activeCount > 0 && !filtersOpen && (
                <span style={{ fontSize: 10, color: 'var(--muted)' }}>
                  {regionFilter !== 'all' ? regionFilter : ''}
                  {productFilter !== 'all' ? ` · ${filterOptions.products.find(p => p.id === productFilter)?.name || ''}` : ''}
                  {supplierFilter !== 'all' ? ` · ${filterOptions.suppliers.find(s => String(s.id) === String(supplierFilter))?.name || ''}` : ''}
                  {materialFilter !== 'all' ? ` · ${materialFilter}` : ''}
                </span>
              )}
            </button>
            {filtersOpen && (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', padding: '0 16px 14px 16px' }}>
                <div style={{ flex: 1, minWidth: 120 }}>
                  <label className="ca-label">Region</label>
                  <select className="ca-select" value={regionFilter} onChange={e => setRegionFilter(e.target.value)}>
                    <option value="all">All Regions</option>
                    {regions.map(r => <option key={r}>{r}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1, minWidth: 120 }}>
                  <label className="ca-label">Product</label>
                  <select className="ca-select" value={productFilter} onChange={e => setProductFilter(e.target.value)}>
                    <option value="all">All Products</option>
                    {filterOptions.products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1, minWidth: 120 }}>
                  <label className="ca-label">Supplier</label>
                  <select className="ca-select" value={supplierFilter} onChange={e => setSupplierFilter(e.target.value)}>
                    <option value="all">All Suppliers</option>
                    {filterOptions.suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1, minWidth: 120 }}>
                  <label className="ca-label">Material</label>
                  <select className="ca-select" value={materialFilter} onChange={e => setMaterialFilter(e.target.value)}>
                    <option value="all">All Materials</option>
                    {materialNames.map(m => <option key={m}>{m}</option>)}
                  </select>
                </div>
                <div style={{ minWidth: 110 }}>
                  <label className="ca-label">From</label>
                  <select className="ca-select" value={startPeriod} onChange={e => setStartPeriod(e.target.value)}>
                    <option value="">Earliest</option>
                    {periodOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div style={{ minWidth: 110 }}>
                  <label className="ca-label">To</label>
                  <select className="ca-select" value={endPeriod} onChange={e => setEndPeriod(e.target.value)}>
                    <option value="">Latest</option>
                    {periodOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                {activeCount > 0 && (
                  <button
                    className="ca-btn ca-btn-ghost ca-btn-sm"
                    style={{ fontSize: 10, marginBottom: 2 }}
                    onClick={() => {
                      setRegionFilter('all');
                      setProductFilter('all');
                      setSupplierFilter('all');
                      setMaterialFilter('all');
                      setStartPeriod('2023-1');
                      setEndPeriod('2026-1');
                    }}
                  >
                    Clear All
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })()}

      {/* Table */}
      <div className="ca-card">
        {loading ? (
          <div style={{ padding: 20, color: 'var(--muted)' }}>Loading...</div>
        ) : periods.length === 0 ? (
          <div style={{ padding: 20, color: 'var(--muted)' }}>No index data available for the selected filters.</div>
        ) : (
          <div className="ca-scroll-x" ref={tableScrollRef}>
            <table className="ca-table">
              <thead>
                <tr>
                  <th style={{ width: 28 }}></th>
                  <th>Material</th>
                  <th>Region</th>
                  {periods.map(p => <th key={p.label} className="center">{p.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const rowKey = `${r.mat}__${r.reg}`;
                  const isExpanded = expandedRow === rowKey;
                  const healthClass = getHealthClass(r.commodity_id, r.reg);
                  const comm = commodityMap.get(r.commodity_id);

                  return [
                    <tr key={rowKey}>
                      <td style={{ padding: '9px 6px', textAlign: 'center' }}>
                        <span
                          className={`idx-chevron${isExpanded ? ' open' : ''}`}
                          onClick={() => setExpandedRow(isExpanded ? null : rowKey)}
                        >
                          &#9654;
                        </span>
                      </td>
                      <td style={{ fontWeight: 500 }}>
                        <span
                          style={{ cursor: 'pointer', borderBottom: '1px dotted var(--muted)' }}
                          onClick={() => handleMaterialClick(r)}
                        >
                          {r.mat}
                        </span>
                        {comm?.unit && (
                          <span style={{ fontSize: 9, color: 'var(--muted)', marginLeft: 6 }}>
                            ({comm.unit})
                          </span>
                        )}
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <span className="ca-tag">{r.reg}</span>
                        <span className={`idx-health ${healthClass}`} title={getHealthTitle(r.commodity_id, r.reg)} />
                      </td>
                      {r.cells.map((cell, vi) => {
                        const v = cell?.value ?? null;
                        if (v === null) {
                          return (
                            <td key={vi} className="center"
                              style={{ color: 'var(--muted)', cursor: 'pointer' }}
                              onClick={() => handleCellClick(cell || {
                                commodity_id: r.commodity_id,
                                commodity_name: r.mat,
                                region: r.reg,
                                year: periods[vi].year,
                                quarter: periods[vi].quarter,
                                value: null,
                                source: 'scraped',
                              })}
                            >
                              {'\u2014'}
                            </td>
                          );
                        }
                        const ratio = r.base ? v / r.base : 1;
                        const cls = ratio > 1.05 ? 'idx-up' : ratio < 0.95 ? 'idx-down' : 'idx-neutral';
                        const isOverride = cell?.source === 'team_override';
                        const overrideTitle = isOverride
                          ? `Override${cell.override_by ? ` by ${cell.override_by}` : ''}${cell.override_at ? ` on ${new Date(cell.override_at).toLocaleDateString()}` : ''} | Click to edit`
                          : `${((ratio - 1) * 100).toFixed(1)}% vs base\nClick to edit`;

                        return (
                          <td key={vi}
                            className={`center ${cls}${isOverride ? ' idx-override' : ''}`}
                            title={overrideTitle}
                            style={{ cursor: 'pointer' }}
                            onClick={() => handleCellClick(cell)}
                          >
                            {v.toLocaleString(undefined, { maximumFractionDigits: 3 })}
                          </td>
                        );
                      })}
                    </tr>,
                    isExpanded && (
                      <tr key={`${rowKey}-detail`} className="idx-detail-row">
                        <td colSpan={periods.length + 3}>
                          <IndexDetailPanel
                            commodity_id={r.commodity_id}
                            commodity_name={r.mat}
                            region={r.reg}
                            teamId={activeTeamId}
                            source={findSource(r.commodity_id, r.reg)}
                            globalScraper={getGlobalScraperInfo(r.commodity_id)}
                            onSourceChanged={handleSourceChanged}
                            onRemoved={handleRowRemoved}
                          />
                        </td>
                      </tr>
                    ),
                  ];
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Cell Modal */}
      <EditCellModal
        isOpen={!!editModal}
        onClose={() => setEditModal(null)}
        cell={editModal}
        teamId={activeTeamId}
        teamSource={editModal ? findSource(editModal.commodity_id, editModal.region) : null}
        periods={periods}
        onSaved={handleEditSaved}
      />

      {/* Add Index Modal */}
      <AddIndexModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        commodities={commodities}
        teamId={activeTeamId}
        onAdded={fetchData}
      />

      {/* Index Popup Modal */}
      <IndexPopupModal
        isOpen={!!popupRow}
        onClose={() => setPopupRow(null)}
        commodityId={popupRow?.commodity_id}
        commodityName={popupRow?.mat}
        region={popupRow?.reg}
        teamId={activeTeamId}
        commodity={popupRow?.commodity}
        periods={periods}
        cellData={popupRow?.cells}
        source={popupRow ? findSource(popupRow.commodity_id, popupRow.reg) : null}
        globalScraper={popupRow ? getGlobalScraperInfo(popupRow.commodity_id) : null}
        onSourceChanged={handleSourceChanged}
        onRemoved={handleRowRemoved}
      />
    </div>
  );
}
