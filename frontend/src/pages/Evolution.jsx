import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import EvoChart from '../components/EvoChart';
import { PIE_COLORS } from '../utils/constants';
import api from '../api';
import exportCsv from '../utils/exportCsv';

function qLabel(y, q) { return `Q${q}-${String(y).slice(-2)}`; }

function generateQuarterOptions(minY, minQ, maxY, maxQ) {
  const opts = [];
  let y = minY, q = minQ;
  while (y < maxY || (y === maxY && q <= maxQ)) {
    opts.push({ year: y, quarter: q, label: qLabel(y, q) });
    q++;
    if (q > 4) { q = 1; y++; }
  }
  return opts;
}

export default function Evolution() {
  const { costModelId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Period range (set after first load from backend defaults)
  const [fromYear, setFromYear] = useState(null);
  const [fromQuarter, setFromQuarter] = useState(null);
  const [toYear, setToYear] = useState(null);
  const [toQuarter, setToQuarter] = useState(null);
  const [formulaMode, setFormulaMode] = useState('active');

  // Component visibility toggles
  const [visibleComponents, setVisibleComponents] = useState({});

  const fetchEvolution = (fy, fq, ty, tq) => {
    if (!costModelId) return;
    setLoading(true);
    const body = {
      cost_model_id: costModelId,
      granularity: 'quarterly',
      formula_mode: formulaMode,
    };
    if (fy && fq) { body.from_year = fy; body.from_quarter = fq; }
    if (ty && tq) { body.to_year = ty; body.to_quarter = tq; }

    api.post('/api/costing/evolution', body)
      .then(({ data }) => {
        setData(data);
        setError(null);
        // Sync period state from what the backend actually returned
        if (data.periods?.length) {
          const first = data.periods[0];
          const last = data.periods[data.periods.length - 1];
          if (!fy) { setFromYear(first.year); setFromQuarter(first.quarter); }
          if (!ty) { setToYear(last.year); setToQuarter(last.quarter); }
        }
        // Ensure all components (including new ones from a mode switch) are visible
        setVisibleComponents(prev => {
          const all = {};
          (data.components || []).forEach(c => { all[c.label] = prev[c.label] ?? true; });
          if (data.periods?.some(p => p.theoretical > 0)) all['Margin'] = prev['Margin'] ?? true;
          return all;
        });
      })
      .catch(err => setError(err.response?.data?.detail || 'Failed to load'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchEvolution(fromYear, fromQuarter, toYear, toQuarter); }, [costModelId, formulaMode]);

  const onChangeFrom = (val) => {
    const [y, q] = val.split('-').map(Number);
    setFromYear(y); setFromQuarter(q);
    fetchEvolution(y, q, toYear, toQuarter);
  };
  const onChangeTo = (val) => {
    const [y, q] = val.split('-').map(Number);
    setToYear(y); setToQuarter(q);
    fetchEvolution(fromYear, fromQuarter, y, q);
  };

  // Build component series for the chart (including margin as a virtual component)
  const componentSeries = useMemo(() => {
    if (!data?.components || !data?.periods) return [];
    const series = data.components.map((comp, i) => ({
      label: comp.label,
      color: PIE_COLORS[i % PIE_COLORS.length],
      visible: !!visibleComponents[comp.label],
      values: data.periods.map(p => p.component_costs?.[comp.label] ?? 0),
    }));
    // Add margin as the residual between should-cost and sum of components
    const marginValues = data.periods.map((p, pi) => {
      const compSum = series.reduce((sum, cs) => sum + cs.values[pi], 0);
      return Math.max(0, p.theoretical - compSum);
    });
    if (marginValues.some(v => v > 0.0001)) {
      series.push({
        label: 'Margin',
        color: PIE_COLORS[series.length % PIE_COLORS.length],
        visible: !!visibleComponents['Margin'],
        values: marginValues,
      });
    }
    return series;
  }, [data, visibleComponents]);

  const toggleComponent = (label) => {
    setVisibleComponents(prev => ({ ...prev, [label]: !prev[label] }));
  };

  const anyVisible = Object.values(visibleComponents).some(Boolean);
  const toggleAll = () => {
    if (!componentSeries.length) return;
    if (anyVisible) {
      setVisibleComponents({});
    } else {
      const all = {};
      componentSeries.forEach(c => { all[c.label] = true; });
      setVisibleComponents(all);
    }
  };

  if (loading && !data) return <div className="ca-page" style={{ color: 'var(--muted)' }}>Loading...</div>;
  if (error) return <div className="ca-page" style={{ color: 'var(--accent2)' }}>Error: {error}</div>;
  if (!data) return null;

  const { periods, product_name, supplier_name, reference_cost, region, currency, unit } = data;
  const theoretical = periods.map(p => p.theoretical);
  const actual = periods.map(p => p.actual ?? 0);
  const periodLabels = periods.map(p => p.period);
  const lastActualPeriod = [...periods].reverse().find(p => p.actual !== null);
  const sym = currency === 'EUR' ? '\u20AC' : '$';

  // Quarter picker options bounded by available index data
  const quarterOpts = (data.available_from_year && data.available_to_year)
    ? generateQuarterOptions(data.available_from_year, data.available_from_quarter, data.available_to_year, data.available_to_quarter)
    : [];

  return (
    <div className="ca-page ca-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div className="ca-h1">Cost Evolution</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}`)}>View Model</button>
          <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}/pricing`)}>Pricing</button>
          <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}/brief`)}>Brief</button>
          <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={() => exportCsv(
            `evolution_${product_name}.csv`,
            ['Period', 'Should-Cost', 'Actual', 'Gap', 'Gap %'],
            periods.map(p => [p.period, p.theoretical, p.actual, p.gap, p.gap_pct])
          )}>Export CSV</button>
        </div>
      </div>
      <p className="ca-subtitle">{product_name}{supplier_name ? ` · ${supplier_name}` : ''} · {region} · Ref: {sym}{reference_cost?.toFixed(2)}</p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
        <div className="ca-metric">
          <div className="ca-metric-lbl">Latest Should-Cost</div>
          <div className="ca-metric-val" style={{ color: 'var(--accent)' }}>{sym}{theoretical[theoretical.length - 1]?.toFixed(3)}</div>
        </div>
        <div className="ca-metric">
          <div className="ca-metric-lbl">Gap (Actual - Should-Cost)</div>
          <div className="ca-metric-val" style={{ color: lastActualPeriod?.gap > 0 ? 'var(--accent2)' : 'var(--accent)' }}>
            {lastActualPeriod ? `${lastActualPeriod.gap > 0 ? '+' : ''}${sym}${lastActualPeriod.gap.toFixed(3)}` : '\u2014'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--muted)' }}>
            {lastActualPeriod ? `${lastActualPeriod.gap_pct?.toFixed(1)}% at ${lastActualPeriod.period}` : ''}
          </div>
        </div>
      </div>

      <div className="ca-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div className="ca-card-title" style={{ margin: 0 }}>Evolution Chart</div>
          {quarterOpts.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <select
                className="ca-select"
                style={{ fontSize: 11, padding: '4px 8px', width: 'auto' }}
                value={fromYear && fromQuarter ? `${fromYear}-${fromQuarter}` : ''}
                onChange={e => onChangeFrom(e.target.value)}
              >
                {quarterOpts.map(o => (
                  <option key={o.label} value={`${o.year}-${o.quarter}`}>{o.label}</option>
                ))}
              </select>
              <span style={{ fontSize: 10, color: 'var(--muted)' }}>to</span>
              <select
                className="ca-select"
                style={{ fontSize: 11, padding: '4px 8px', width: 'auto' }}
                value={toYear && toQuarter ? `${toYear}-${toQuarter}` : ''}
                onChange={e => onChangeTo(e.target.value)}
              >
                {quarterOpts.map(o => (
                  <option key={o.label} value={`${o.year}-${o.quarter}`}>{o.label}</option>
                ))}
              </select>
              <select
                className="ca-select"
                style={{ fontSize: 11, padding: '4px 8px', width: 'auto' }}
                value={formulaMode}
                onChange={e => setFormulaMode(e.target.value)}
              >
                <option value="active">Active Model</option>
                <option value="versioned">Versioned</option>
              </select>
            </div>
          )}
        </div>
        <div className="ca-scroll-x">
          <EvoChart
            periods={periodLabels}
            theoretical={theoretical}
            actual={actual}
            refCost={reference_cost}
            componentSeries={componentSeries}
          />
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 20, marginTop: 14, fontSize: 11, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 2, background: 'var(--accent4)' }} /> Actual
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 20, height: 0, borderTop: '2px dashed var(--accent)' }} /> Should-Cost
          </div>
          {componentSeries.filter(cs => cs.visible).map((cs, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 10, height: 10, background: cs.color, borderRadius: 2, opacity: 0.85 }} /> {cs.label}
            </div>
          ))}
        </div>

        {/* Component toggles */}
        {componentSeries.length > 0 && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', marginRight: 4 }}>Components</span>
              <button
                className="ca-btn ca-btn-sm ca-btn-ghost"
                style={{ fontSize: 10, padding: '2px 8px' }}
                onClick={toggleAll}
              >
                {anyVisible ? 'Hide All' : 'Show All'}
              </button>
              {componentSeries.map((cs) => {
                const isOn = cs.visible;
                return (
                  <button
                    key={cs.label}
                    onClick={() => toggleComponent(cs.label)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 5,
                      padding: '3px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
                      border: `1px solid ${isOn ? cs.color : 'var(--border)'}`,
                      background: isOn ? `${cs.color}18` : 'transparent',
                      color: isOn ? cs.color : 'var(--muted)',
                      transition: 'all .15s',
                    }}
                  >
                    <div style={{ width: 7, height: 7, borderRadius: 2, background: isOn ? cs.color : 'var(--border)' }} />
                    {cs.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="ca-card">
        <div className="ca-card-title">Detail Table</div>
        <div className="ca-scroll-x">
          <table className="ca-table">
            <thead><tr><th>Metric</th>{periods.map(p => <th key={p.period} className="center">{p.period}</th>)}</tr></thead>
            <tbody>
              <tr style={{ background: 'rgba(79,255,176,.03)' }}>
                <td>Actual</td>
                {periods.map((p, i) => <td key={i} className="center" style={{ color: 'var(--accent4)', fontWeight: 500 }}>{p.actual !== null ? `${sym}${p.actual.toFixed(3)}` : '\u2014'}</td>)}
              </tr>
              <tr>
                <td>Should-Cost</td>
                {periods.map((p, i) => <td key={i} className="center" style={{ color: 'var(--accent)' }}>{sym}{p.theoretical.toFixed(3)}</td>)}
              </tr>
              <tr>
                <td>Gap ($)</td>
                {periods.map((p, i) => <td key={i} className="center" style={{ color: p.gap > 0 ? 'var(--accent2)' : p.gap < 0 ? 'var(--accent)' : 'var(--muted)' }}>{p.gap !== null ? `${p.gap > 0 ? '+' : ''}${sym}${p.gap.toFixed(3)}` : '\u2014'}</td>)}
              </tr>
              <tr>
                <td>Gap (%)</td>
                {periods.map((p, i) => <td key={i} className="center" style={{ color: p.gap_pct > 0 ? 'var(--accent2)' : p.gap_pct < 0 ? 'var(--accent)' : 'var(--muted)' }}>{p.gap_pct !== null ? `${p.gap_pct > 0 ? '+' : ''}${p.gap_pct.toFixed(1)}%` : '\u2014'}</td>)}
              </tr>
              {[...componentSeries].filter(cs => cs.visible).reverse().map((cs, i) => (
                <tr key={cs.label} style={{ background: `${cs.color}08` }}>
                  <td style={{ color: cs.color }}>{cs.label}</td>
                  {cs.values.map((v, j) => (
                    <td key={j} className="center" style={{ fontSize: 11, color: cs.color }}>
                      {sym}{v.toFixed(3)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
