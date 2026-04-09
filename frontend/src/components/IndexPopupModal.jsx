import { useState, useEffect } from 'react';
import api from '../api';
import IndexTrendChart from './IndexTrendChart';
import IndexDetailPanel from './IndexDetailPanel';

/**
 * Full-screen modal showing index details: trend chart, AI summary,
 * portfolio impact, and source controls.
 */
export default function IndexPopupModal({
  isOpen,
  onClose,
  commodityId,
  commodityName,
  region,
  teamId,
  commodity,       // CommodityIndexOut object (unit, currency, category, source_url)
  periods,         // [{year, quarter, label}, ...]
  cellData,        // array of cell values matching periods (for chart)
  source,          // TeamIndexSource or null
  globalScraper,   // {scraper, scrape_at} or null
  onSourceChanged,
  onRemoved,
}) {
  const [impacts, setImpacts] = useState([]);
  const [loadingImpacts, setLoadingImpacts] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [loadingAi, setLoadingAi] = useState(false);

  useEffect(() => {
    if (!isOpen || !commodityId || !teamId) return;
    setLoadingImpacts(true);
    api.get(`/api/indexes/${commodityId}/impact`, { params: { team_id: teamId } })
      .then(res => setImpacts(res.data.impacts || []))
      .catch(() => setImpacts([]))
      .finally(() => setLoadingImpacts(false));
  }, [isOpen, commodityId, teamId]);

  // Fetch AI analysis once impacts are loaded
  useEffect(() => {
    if (!isOpen || !commodityId || loadingImpacts) return;
    setLoadingAi(true);
    setAiAnalysis(null);
    api.post('/api/ai/index-analysis', {
      commodity_id: commodityId,
      commodity_name: commodityName,
      region,
      category: commodity?.category,
      unit: commodity?.unit,
      currency: commodity?.currency,
      periods: cellData?.filter(c => c?.value != null).map(c => ({
        year: c.year, quarter: c.quarter, value: c.value,
      })) || [],
      impacts: impacts.map(i => ({
        product_name: i.product_name,
        supplier_name: i.supplier_name,
        weight: i.weight,
        index_change_pct: i.index_change_pct,
        cost_impact_pct: i.cost_impact_pct,
      })),
    })
      .then(res => setAiAnalysis(res.data))
      .catch(() => setAiAnalysis({ analysis: 'AI analysis unavailable.', source: 'error' }))
      .finally(() => setLoadingAi(false));
  }, [isOpen, commodityId, loadingImpacts]);

  if (!isOpen) return null;

  const chartValues = periods.map((p) => {
    const cell = cellData?.find(c => c?.year === p.year && c?.quarter === p.quarter);
    return cell?.value ?? null;
  });

  const categoryColors = {
    Metal: '#5B8AF0', Energy: '#F0A35B', Chemical: '#A35BF0',
    Labor: '#5BF0A3', PPI: '#F05B8A', Freight: '#8AF05B', FX: '#F0F05B',
  };

  return (
    <div className="ca-modal-backdrop" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 740, width: '95vw' }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="ca-modal-header" style={{ alignItems: 'flex-start' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 15 }}>{commodityName}</span>
              {commodity?.category && (
                <span className="ca-badge" style={{
                  background: categoryColors[commodity.category] || 'var(--accent-dim)',
                  color: '#fff', fontSize: 9,
                }}>
                  {commodity.category}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6, display: 'flex', gap: 16 }}>
              {commodity?.unit && <span>Unit: <strong>{commodity.unit}</strong></span>}
              {commodity?.currency && <span>Currency: <strong>{commodity.currency}</strong></span>}
              {region && <span>Region: <strong>{region}</strong></span>}
            </div>
            {commodity?.source_url && (
              <a href={commodity.source_url} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 10, color: 'var(--accent4)', textDecoration: 'underline', marginTop: 4, display: 'inline-block' }}>
                {commodity.source_url.length > 70 ? commodity.source_url.slice(0, 70) + '...' : commodity.source_url}
              </a>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: 'var(--muted)',
              cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: 4,
            }}
          >
            &times;
          </button>
        </div>

        <div className="ca-modal-body">
        {/* Trend Chart */}
        <div className="ca-card" style={{ marginBottom: 16, padding: '12px 8px' }}>
          <div className="ca-card-title" style={{ marginBottom: 8 }}>Price Trend</div>
          <IndexTrendChart periods={periods} values={chartValues} unit={commodity?.unit} />
        </div>

        {/* AI Analysis */}
        <div className="ca-card" style={{ marginBottom: 16, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: 14 }}>&#10024;</span>
            <span className="ca-card-title" style={{ margin: 0 }}>AI Analysis</span>
          </div>
          {loadingAi ? (
            <p style={{ color: 'var(--muted)', fontSize: 11, fontStyle: 'italic', margin: 0 }}>
              Generating analysis...
            </p>
          ) : aiAnalysis ? (
            <p style={{ fontSize: 12, lineHeight: 1.8, color: 'var(--text-secondary)', margin: 0 }}>
              {aiAnalysis.analysis}
            </p>
          ) : null}
        </div>

        {/* Portfolio Impact */}
        <div className="ca-card" style={{ marginBottom: 16 }}>
          <div className="ca-card-title" style={{ marginBottom: 8 }}>Portfolio Impact</div>
          {loadingImpacts ? (
            <div style={{ color: 'var(--muted)', fontSize: 11, padding: 8 }}>Loading...</div>
          ) : impacts.length === 0 ? (
            <div style={{ color: 'var(--muted)', fontSize: 11, padding: 8 }}>
              No products in your portfolio use this index.
            </div>
          ) : (
            <div className="ca-scroll-x">
              <table className="ca-table" style={{ fontSize: 11 }}>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Supplier</th>
                    <th>Component</th>
                    <th className="center">Weight</th>
                    <th className="center">Index Change</th>
                    <th className="center">Cost Impact</th>
                  </tr>
                </thead>
                <tbody>
                  {impacts.map((imp, i) => (
                    <tr key={i}>
                      <td>{imp.product_name}</td>
                      <td>{imp.supplier_name || '\u2014'}</td>
                      <td>{imp.component_label}</td>
                      <td className="center">{(imp.weight * 100).toFixed(1)}%</td>
                      <td className="center" style={{
                        color: imp.index_change_pct > 0 ? 'var(--accent2)' :
                               imp.index_change_pct < 0 ? 'var(--accent)' : 'var(--muted)',
                      }}>
                        {imp.index_change_pct != null ? `${imp.index_change_pct > 0 ? '+' : ''}${imp.index_change_pct.toFixed(1)}%` : '\u2014'}
                      </td>
                      <td className="center" style={{
                        color: imp.cost_impact_pct > 0 ? 'var(--accent2)' :
                               imp.cost_impact_pct < 0 ? 'var(--accent)' : 'var(--muted)',
                        fontWeight: 600,
                      }}>
                        {imp.cost_impact_pct != null ? `${imp.cost_impact_pct > 0 ? '+' : ''}${imp.cost_impact_pct.toFixed(2)}%` : '\u2014'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Source & Controls (reuse IndexDetailPanel) */}
        <div className="ca-card" style={{ marginBottom: 0 }}>
          <div className="ca-card-title" style={{ marginBottom: 8 }}>Source & Controls</div>
          <IndexDetailPanel
            commodity_id={commodityId}
            commodity_name={commodityName}
            region={region}
            teamId={teamId}
            source={source}
            globalScraper={globalScraper}
            onSourceChanged={onSourceChanged}
            onRemoved={onRemoved}
          />
        </div>
        </div>
      </div>
    </div>
  );
}
