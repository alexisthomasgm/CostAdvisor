import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { OVC_ITEMS, RM_ITEMS, PIE_COLORS } from '../utils/constants';
import DonutChart from '../components/DonutChart';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function CostModelBuilder() {
  const { costModelId } = useParams();
  const navigate = useNavigate();
  const { activeTeamId } = useAuth();
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(!costModelId);
  const [editing, setEditing] = useState(!costModelId);

  const [products, setProducts] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [commodities, setCommodities] = useState([]);

  // Product fields
  const [productId, setProductId] = useState('');
  const [productName, setProductName] = useState('');
  const [formula, setFormula] = useState('');
  const [activeContent, setActiveContent] = useState(0.65);
  const [unit, setUnit] = useState('kg');

  // Cost model fields
  const [supplierId, setSupplierId] = useState('');
  const [newSupplierName, setNewSupplierName] = useState('');
  const [destinationCountry, setDestinationCountry] = useState('');
  const [region, setRegion] = useState('Europe');
  const [currency, setCurrency] = useState('USD');

  // Formula version fields
  const [basePrice, setBasePrice] = useState(3.0);
  const [baseYear, setBaseYear] = useState(2024);
  const [baseQuarter, setBaseQuarter] = useState(1);
  const [marginType, setMarginType] = useState('pct');
  const [marginValue, setMarginValue] = useState(20);
  const [components, setComponents] = useState([
    { label: 'Oil Price', commodity_name: 'Oil Price', parts: 41 },
    { label: 'Chlorine', commodity_name: 'Chlorine', parts: 3 },
    { label: 'Energy & Utilities', commodity_name: 'Energy & Utilities', parts: 7 },
    { label: 'Direct Labor', commodity_name: 'Direct Labor Costs', parts: 10 },
    { label: 'PPI Manufacturing', commodity_name: 'PPI Manufacturing Europe', parts: 26 },
    { label: 'Freight', commodity_name: 'Container Freight WCI', parts: 13 },
  ]);

  // Snapshot for cancel
  const [snapshot, setSnapshot] = useState(null);

  // Resolved supplier name for view mode
  const supplierName = useMemo(() => {
    if (!supplierId) return newSupplierName || null;
    const s = suppliers.find(s => String(s.id) === String(supplierId));
    return s ? s.name : null;
  }, [supplierId, newSupplierName, suppliers]);

  // Load reference data
  useEffect(() => {
    if (!activeTeamId) return;
    Promise.all([
      api.get('/api/products', { params: { team_id: activeTeamId } }),
      api.get('/api/suppliers', { params: { team_id: activeTeamId } }),
      api.get('/api/indexes'),
    ]).then(([pRes, sRes, iRes]) => {
      setProducts(pRes.data);
      setSuppliers(sRes.data);
      setCommodities(iRes.data);
    }).catch(console.error);
  }, [activeTeamId]);

  // Load existing cost model
  useEffect(() => {
    if (!costModelId) return;
    api.get(`/api/cost-models/${costModelId}`)
      .then(({ data }) => {
        setProductId(data.product_id);
        setProductName(data.product_name || '');
        setFormula(data.product_reference || '');
        setUnit(data.product_unit || 'kg');
        setActiveContent(data.product_active_content ?? 0.65);
        setSupplierId(data.supplier_id || '');
        setDestinationCountry(data.destination_country || '');
        setRegion(data.region);
        setCurrency(data.currency);

        const currentFv = data.formula_versions?.[0];
        if (currentFv) {
          setBasePrice(currentFv.base_price);
          setBaseYear(currentFv.base_year);
          setBaseQuarter(currentFv.base_quarter);
          setMarginType(currentFv.margin_type === 'pct' || currentFv.margin_type === 'fixed' ? currentFv.margin_type : 'pct');
          setMarginValue(currentFv.margin_value ?? 20);

          setComponents(currentFv.components.map(c => ({
            label: c.label,
            commodity_name: c.commodity_name || '',
            commodity_id: c.commodity_id,
            parts: Math.round(c.weight * 100),
          })));
        }
        setLoaded(true);
      })
      .catch(err => { console.error(err); setLoaded(true); });
  }, [costModelId]);

  // Computed
  const totalParts = components.reduce((s, c) => s + (c.parts || 0), 0);
  const marginCost = marginType === 'pct'
    ? basePrice * (marginValue || 0) / 100
    : (marginValue || 0);
  const componentPool = basePrice - marginCost;
  const marginWeight = basePrice > 0 ? marginCost / basePrice : 0;
  const isValid = totalParts > 0 && componentPool >= 0 && basePrice > 0;

  const compWeight = (c) => totalParts > 0 ? (c.parts / totalParts) * (componentPool / basePrice) : 0;
  const compCost = (c) => totalParts > 0 ? (c.parts / totalParts) * componentPool : 0;

  const shouldCost = basePrice;

  const donutSegs = useMemo(() => {
    const segs = components
      .filter(c => c.parts > 0)
      .map((c, i) => ({
        label: c.label,
        pct: totalParts > 0 ? (c.parts / totalParts) * (1 - marginWeight) : 0,
        color: PIE_COLORS[i % PIE_COLORS.length],
      }));
    if (marginWeight > 0) {
      segs.push({ label: 'Margin', pct: marginWeight, color: 'var(--accent2)' });
    }
    return segs;
  }, [components, totalParts, marginWeight]);

  const startEditing = () => {
    setSnapshot({
      productName, formula, activeContent, unit,
      supplierId, newSupplierName, destinationCountry, region, currency,
      basePrice, baseYear, baseQuarter, marginType, marginValue,
      components: components.map(c => ({ ...c })),
    });
    setEditing(true);
  };

  const cancelEditing = () => {
    if (snapshot) {
      setProductName(snapshot.productName);
      setFormula(snapshot.formula);
      setActiveContent(snapshot.activeContent);
      setUnit(snapshot.unit);
      setSupplierId(snapshot.supplierId);
      setNewSupplierName(snapshot.newSupplierName);
      setDestinationCountry(snapshot.destinationCountry);
      setRegion(snapshot.region);
      setCurrency(snapshot.currency);
      setBasePrice(snapshot.basePrice);
      setBaseYear(snapshot.baseYear);
      setBaseQuarter(snapshot.baseQuarter);
      setMarginType(snapshot.marginType);
      setMarginValue(snapshot.marginValue);
      setComponents(snapshot.components);
    }
    setEditing(false);
    setSnapshot(null);
  };

  const save = async () => {
    setSaving(true);
    try {
      let pid = productId;
      if (!pid) {
        const { data } = await api.post(`/api/products?team_id=${activeTeamId}`, {
          name: productName,
          formula,
          active_content: activeContent,
          unit,
        });
        pid = data.id;
      }

      let sid = supplierId || null;
      if (!sid && newSupplierName) {
        const { data } = await api.post(`/api/suppliers?team_id=${activeTeamId}`, {
          name: newSupplierName,
        });
        sid = data.id;
      }

      const payload = {
        product_id: pid,
        supplier_id: sid ? Number(sid) : null,
        destination_country: destinationCountry || null,
        region,
        currency,
        formula: {
          base_price: basePrice,
          base_year: baseYear,
          base_quarter: baseQuarter,
          margin_type: marginType,
          margin_value: marginValue,
          components: components.map(c => ({
            label: c.label,
            commodity_name: c.commodity_name || null,
            weight: totalParts > 0 ? c.parts / totalParts : 0,
          })),
        },
      };

      if (costModelId) {
        if (pid) {
          await api.put(`/api/products/${pid}`, {
            name: productName,
            formula: formula || null,
            active_content: activeContent,
            unit,
          });
        }
        await api.put(`/api/cost-models/${costModelId}`, {
          supplier_id: sid ? Number(sid) : null,
          destination_country: destinationCountry || null,
          region,
          currency,
        });
        await api.post(`/api/cost-models/${costModelId}/renegotiate`, payload.formula);
        setEditing(false);
        setSnapshot(null);
      } else {
        const { data } = await api.post(`/api/cost-models?team_id=${activeTeamId}`, payload);
        navigate(`/cost-models/${data.id}`, { replace: true });
      }
    } catch (err) {
      alert('Error saving: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const updateComp = (i, key, val) => {
    const next = [...components];
    next[i] = { ...next[i], [key]: val };
    setComponents(next);
  };
  const addComp = () => setComponents([...components, { label: '', commodity_name: '', parts: 0 }]);
  const removeComp = (i) => setComponents(components.filter((_, j) => j !== i));

  if (!loaded) return <div className="ca-page" style={{ color: 'var(--muted)' }}>Loading...</div>;

  const sym = currency === 'EUR' ? '\u20AC' : '$';

  return (
    <div className="ca-page ca-fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div className="ca-h1">
          {!costModelId ? 'New Cost Model' : editing ? 'Edit Cost Model' : 'Cost Model'}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {costModelId && (
            <>
              <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}/pricing`)}>
                Pricing
              </button>
              <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}/evolution`)}>
                Evolution
              </button>
              <button className="ca-btn ca-btn-ghost" onClick={() => navigate(`/cost-models/${costModelId}/brief`)}>
                Brief
              </button>
            </>
          )}
          {editing ? (
            <>
              {costModelId && (
                <button className="ca-btn ca-btn-ghost" onClick={cancelEditing}>Cancel</button>
              )}
              <button className="ca-btn ca-btn-primary" onClick={save} disabled={saving || !isValid}>
                {saving ? 'Saving...' : (costModelId ? 'Save' : 'Create')}
              </button>
            </>
          ) : (
            <button className="ca-btn ca-btn-primary" onClick={startEditing}>Edit</button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 22, alignItems: 'start' }}>
        {/* LEFT COLUMN */}
        <div>
          {/* Supplier & Destination */}
          <div className="ca-card" style={{ marginBottom: 16 }}>
            <div className="ca-card-title">Supplier & Destination</div>
            {editing ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label className="ca-label">Supplier</label>
                  <select className="ca-select" value={supplierId} onChange={e => setSupplierId(e.target.value)}>
                    <option value="">— New supplier —</option>
                    {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
                {!supplierId && (
                  <div>
                    <label className="ca-label">New Supplier Name</label>
                    <input className="ca-input" value={newSupplierName} onChange={e => setNewSupplierName(e.target.value)} />
                  </div>
                )}
                <div>
                  <label className="ca-label">Destination Country</label>
                  <input className="ca-input" value={destinationCountry} onChange={e => setDestinationCountry(e.target.value)} />
                </div>
                <div>
                  <label className="ca-label">Region</label>
                  <select className="ca-select" value={region} onChange={e => setRegion(e.target.value)}>
                    {['Europe','NA','Asia','Latam'].map(r => <option key={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <label className="ca-label">Currency</label>
                  <select className="ca-select" value={currency} onChange={e => setCurrency(e.target.value)}>
                    {['USD','EUR'].map(c => <option key={c}>{c}</option>)}
                  </select>
                </div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label className="ca-label">Supplier</label>
                  <div style={{ fontSize: 13, padding: '7px 0' }}>{supplierName || '\u2014'}</div>
                </div>
                <div>
                  <label className="ca-label">Destination Country</label>
                  <div style={{ fontSize: 13, padding: '7px 0' }}>{destinationCountry || '\u2014'}</div>
                </div>
                <div>
                  <label className="ca-label">Region</label>
                  <div style={{ fontSize: 13, padding: '7px 0' }}>{region}</div>
                </div>
                <div>
                  <label className="ca-label">Currency</label>
                  <div style={{ fontSize: 13, padding: '7px 0' }}>{currency}</div>
                </div>
              </div>
            )}
          </div>

          {/* Formula */}
          <div className="ca-card">
            <div className="ca-card-title">Formula Components</div>
            {editing ? (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
                  <div>
                    <label className="ca-label">Total Price ({sym}/unit)</label>
                    <input className="ca-input" type="number" value={basePrice} min={0} step={0.01}
                      onChange={e => setBasePrice(+e.target.value)} />
                  </div>
                  <div>
                    <label className="ca-label">Base Year</label>
                    <select className="ca-select" value={baseYear} onChange={e => setBaseYear(+e.target.value)}>
                      {[2022,2023,2024,2025,2026].map(y => <option key={y} value={y}>{y}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="ca-label">Base Quarter</label>
                    <select className="ca-select" value={baseQuarter} onChange={e => setBaseQuarter(+e.target.value)}>
                      {[1,2,3,4].map(q => <option key={q} value={q}>Q{q}</option>)}
                    </select>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 60px 80px 90px 30px', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase' }}>Label</span>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase' }}>Reference Index</span>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase' }}>Parts</span>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', textAlign: 'right' }}>Weight</span>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', textAlign: 'right' }}>Est. Cost</span>
                  <span></span>
                </div>
                {components.map((c, i) => (
                  <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 60px 80px 90px 30px', gap: 8, marginBottom: 6, alignItems: 'center' }}>
                    <input className="ca-input" value={c.label} placeholder="Component label"
                      onChange={e => updateComp(i, 'label', e.target.value)} style={{ padding: '7px 8px' }} />
                    <select className="ca-select" value={c.commodity_name || ''} style={{ fontSize: 11, padding: '7px 8px' }}
                      onChange={e => updateComp(i, 'commodity_name', e.target.value)}>
                      <option value="">None</option>
                      {commodities.map(ci => <option key={ci.id} value={ci.name}>{ci.name}</option>)}
                    </select>
                    <input className="ca-input" type="number" value={c.parts || 0} min={0}
                      style={{ textAlign: 'right', padding: '7px 6px' }}
                      onChange={e => updateComp(i, 'parts', +e.target.value)} />
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, textAlign: 'right', color: 'var(--muted)' }}>
                      {(compWeight(c) * 100).toFixed(1)}%
                    </span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, textAlign: 'right' }}>
                      {sym}{compCost(c).toFixed(3)}
                    </span>
                    <button className="ca-btn-danger" onClick={() => removeComp(i)}>x</button>
                  </div>
                ))}

                <button className="ca-btn ca-btn-ghost ca-btn-sm" style={{ marginTop: 6, marginBottom: 12 }} onClick={addComp}>
                  + Add Component
                </button>
              </>
            ) : (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
                  <div>
                    <label className="ca-label">Total Price ({sym}/unit)</label>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, padding: '7px 0' }}>{sym}{basePrice.toFixed(3)}</div>
                  </div>
                  <div>
                    <label className="ca-label">Base Period</label>
                    <div style={{ fontSize: 13, padding: '7px 0' }}>Q{baseQuarter}-{baseYear}</div>
                  </div>
                  <div></div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 80px 90px', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase' }}>Label</span>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase' }}>Reference Index</span>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', textAlign: 'right' }}>Weight</span>
                  <span style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', textAlign: 'right' }}>Est. Cost</span>
                </div>
                {components.map((c, i) => (
                  <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 80px 90px', gap: 8, marginBottom: 6, alignItems: 'center' }}>
                    <span style={{ fontSize: 13 }}>{c.label}</span>
                    <span style={{ fontSize: 11, color: 'var(--muted)' }}>{c.commodity_name || '\u2014'}</span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, textAlign: 'right', color: 'var(--muted)' }}>
                      {(compWeight(c) * 100).toFixed(1)}%
                    </span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, textAlign: 'right' }}>
                      {sym}{compCost(c).toFixed(3)}
                    </span>
                  </div>
                ))}
              </>
            )}

            <hr className="ca-sep" />

            {/* Margin section */}
            <div className="ca-card-title" style={{ marginTop: 8 }}>Margin</div>
            {editing ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 70px 70px', gap: 12, marginBottom: 12, alignItems: 'flex-end' }}>
                <div>
                  <label className="ca-label">Type</label>
                  <select className="ca-select" value={marginType} onChange={e => setMarginType(e.target.value)}>
                    <option value="pct">Percentage</option>
                    <option value="fixed">Fixed Amount</option>
                  </select>
                </div>
                <div>
                  <label className="ca-label">{marginType === 'pct' ? 'Margin %' : `Fixed Amount (${sym})`}</label>
                  <input className="ca-input" type="number" value={marginValue} min={0}
                    step={marginType === 'pct' ? 1 : 0.01}
                    onChange={e => setMarginValue(+e.target.value)} />
                </div>
                <div>
                  <label className="ca-label" style={{ fontSize: 9 }}>Weight</label>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, textAlign: 'right', padding: '7px 0', color: 'var(--muted)' }}>
                    {(marginWeight * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <label className="ca-label" style={{ fontSize: 9 }}>Est. Cost</label>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, textAlign: 'right', padding: '7px 0' }}>
                    {sym}{marginCost.toFixed(3)}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 70px 70px', gap: 12, marginBottom: 12, alignItems: 'flex-end' }}>
                <div>
                  <label className="ca-label">Type</label>
                  <div style={{ fontSize: 13, padding: '7px 0' }}>{marginType === 'pct' ? 'Percentage' : 'Fixed Amount'}</div>
                </div>
                <div>
                  <label className="ca-label">Value</label>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, padding: '7px 0' }}>
                    {marginType === 'pct' ? `${marginValue}%` : `${sym}${marginValue}`}
                  </div>
                </div>
                <div>
                  <label className="ca-label" style={{ fontSize: 9 }}>Weight</label>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, textAlign: 'right', padding: '7px 0', color: 'var(--muted)' }}>
                    {(marginWeight * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <label className="ca-label" style={{ fontSize: 9 }}>Est. Cost</label>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, textAlign: 'right', padding: '7px 0' }}>
                    {sym}{marginCost.toFixed(3)}
                  </div>
                </div>
              </div>
            )}

            {editing && componentPool < 0 && (
              <div style={{ fontSize: 11, color: 'var(--accent2)', marginBottom: 8 }}>
                Margin exceeds total price.
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--bg)', borderRadius: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                Components: {sym}{componentPool >= 0 ? componentPool.toFixed(3) : '\u2014'} + Margin: {sym}{marginCost.toFixed(3)}
              </span>
              <span style={{
                fontFamily: "'Syne', sans-serif", fontSize: 16, fontWeight: 700,
                color: isValid ? 'var(--accent)' : 'var(--accent2)'
              }}>
                {sym}{shouldCost.toFixed(3)}
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN */}
        <div>
          {/* Product Family */}
          <div className="ca-card" style={{ marginBottom: 16 }}>
            <div className="ca-card-title">Product Family</div>
            {editing ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ gridColumn: '1 / -1' }}>
                  <label className="ca-label">Product Family</label>
                  <input className="ca-input" placeholder="e.g. Active Carbon" value={productName}
                    onChange={e => setProductName(e.target.value)} />
                </div>
                <div>
                  <label className="ca-label">Product Reference</label>
                  <input className="ca-input" placeholder="e.g. Mineral or Recycled" value={formula} onChange={e => setFormula(e.target.value)} />
                </div>
                <div>
                  <label className="ca-label">Unit</label>
                  <select className="ca-select" value={unit} onChange={e => setUnit(e.target.value)}>
                    {['kg', 't', 'lb'].map(u => <option key={u} value={u}>{u}</option>)}
                  </select>
                </div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ gridColumn: '1 / -1' }}>
                  <label className="ca-label">Product Family</label>
                  <div style={{ fontSize: 13, padding: '7px 0', fontWeight: 600 }}>{productName || '\u2014'}</div>
                </div>
                <div>
                  <label className="ca-label">Product Reference</label>
                  <div style={{ fontSize: 13, padding: '7px 0' }}>{formula || '\u2014'}</div>
                </div>
                <div>
                  <label className="ca-label">Unit</label>
                  <div style={{ fontSize: 13, padding: '7px 0' }}>{unit}</div>
                </div>
              </div>
            )}
          </div>

          {/* Should-Cost result */}
          <div className="ca-result" style={{ marginBottom: 16 }}>
            <div className="ca-result-label">Estimated Should-Cost</div>
            <div className="ca-result-big">{sym}{shouldCost.toFixed(3)}</div>
            <div style={{ marginTop: 4, fontSize: 11, color: 'var(--muted)' }}>
              per {unit} · {region}
            </div>
            <hr className="ca-sep" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 20, fontWeight: 700, color: 'var(--accent3)' }}>
                  {sym}{componentPool >= 0 ? componentPool.toFixed(3) : '\u2014'}
                </div>
                <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase' }}>Indexed Cost</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 20, fontWeight: 700, color: 'var(--accent2)' }}>
                  {sym}{marginCost.toFixed(3)}
                </div>
                <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase' }}>Margin</div>
              </div>
            </div>
          </div>

          {/* Donut chart */}
          <div className="ca-card">
            <div className="ca-card-title">Cost Composition</div>
            <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
              <div style={{ position: 'relative' }}>
                <DonutChart segments={donutSegs} size={150} />
                <div style={{
                  position: 'absolute', top: '50%', left: '50%',
                  transform: 'translate(-50%, -50%)', textAlign: 'center', pointerEvents: 'none'
                }}>
                  <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 16, fontWeight: 700 }}>100%</div>
                  <div style={{ fontSize: 8, color: 'var(--muted)' }}>TOTAL</div>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                {donutSegs.map((s, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5, fontSize: 11 }}>
                    <div style={{ width: 9, height: 9, borderRadius: 2, flexShrink: 0, background: s.color }} />
                    <span style={{ color: 'var(--muted)', flex: 1 }}>{s.label}</span>
                    <span style={{ color: 'var(--text)' }}>{(s.pct * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {costModelId && (
            <VersionHistory costModelId={costModelId} editing={editing} onLoadVersion={(v) => {
              setBasePrice(v.base_price);
              setBaseYear(v.base_year);
              setBaseQuarter(v.base_quarter);
              setMarginType(v.margin_type === 'pct' || v.margin_type === 'fixed' ? v.margin_type : 'pct');
              setMarginValue(v.margin_value ?? 20);
              setComponents(v.components.map(c => ({
                label: c.label,
                commodity_name: c.commodity_name || '',
                commodity_id: c.commodity_id,
                parts: Math.round(c.weight * 100),
              })));
            }} />
          )}
        </div>
      </div>
    </div>
  );
}

function VersionHistory({ costModelId, editing, onLoadVersion }) {
  const [versions, setVersions] = useState([]);
  const [open, setOpen] = useState(false);

  const fetchVersions = () => {
    api.get(`/api/cost-models/${costModelId}/versions`)
      .then(({ data }) => setVersions(data))
      .catch(console.error);
  };

  useEffect(fetchVersions, [costModelId]);

  const deleteVersion = (v) => {
    if (!confirm(`Delete formula for Q${v.base_quarter}-${v.base_year}?`)) return;
    api.delete(`/api/cost-models/${costModelId}/versions/${v.id}`)
      .then(fetchVersions)
      .catch(err => alert('Error: ' + (err.response?.data?.detail || err.message)));
  };

  if (versions.length === 0) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <button
        className="ca-btn ca-btn-ghost"
        style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px' }}
        onClick={() => setOpen(!open)}
      >
        <span style={{ fontSize: 12, fontWeight: 600 }}>Version History ({versions.length})</span>
        <span style={{ fontSize: 10, transition: 'transform .15s', transform: open ? 'rotate(180deg)' : 'rotate(0)' }}>{'\u25BC'}</span>
      </button>
      {open && (
        <div style={{ border: '1px solid var(--border)', borderTop: 'none', borderRadius: '0 0 8px 8px', maxHeight: 220, overflowY: 'auto' }}>
          <table className="ca-table" style={{ margin: 0 }}>
            <thead>
              <tr>
                <th>Quarter</th>
                <th>Base Price</th>
                <th>Margin</th>
                <th>Last Updated</th>
                {editing && <th className="center" style={{ width: 90 }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {versions.map(v => (
                <tr key={v.id}>
                  <td>Q{v.base_quarter}-{v.base_year}</td>
                  <td>${v.base_price.toFixed(2)}</td>
                  <td>{v.margin_type === 'pct' ? `${v.margin_value}%` : v.margin_type === 'fixed' ? `$${v.margin_value}` : 'Unknown'}</td>
                  <td style={{ fontSize: 11, color: 'var(--muted)' }}>{new Date(v.updated_at || v.created_at).toLocaleDateString()}</td>
                  {editing && (
                    <td className="center">
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                        <button
                          className="ca-btn ca-btn-ghost ca-btn-sm"
                          onClick={() => onLoadVersion(v)}
                          title="Load into editor"
                        >Load</button>
                        <button
                          className="ca-btn ca-btn-ghost ca-btn-sm"
                          style={{ color: 'var(--accent2)' }}
                          onClick={() => deleteVersion(v)}
                          disabled={versions.length <= 1}
                          title={versions.length <= 1 ? 'Cannot delete the only version' : 'Delete version'}
                        >Del</button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
