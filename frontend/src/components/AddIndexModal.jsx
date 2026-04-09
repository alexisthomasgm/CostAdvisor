import { useState, useEffect } from 'react';
import Modal from './Modal';
import api from '../api';

export default function AddIndexModal({ isOpen, onClose, commodities, teamId, onAdded }) {
  const [commodityId, setCommodityId] = useState('');
  const [region, setRegion] = useState('');
  const [sourceType, setSourceType] = useState('manual');
  const [scrapeUrl, setScrapeUrl] = useState('');
  const [scrapeConfig, setScrapeConfig] = useState('{}');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [detectedSource, setDetectedSource] = useState(null);

  // Detect source type when URL changes
  useEffect(() => {
    if (!scrapeUrl || scrapeUrl.length < 5) {
      setDetectedSource(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.get('/api/indexes/detect-source', { params: { url: scrapeUrl } });
        setDetectedSource(res.data.detected_source !== 'generic' ? res.data.detected_source : null);
      } catch {
        setDetectedSource(null);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [scrapeUrl]);

  const handleAdd = async () => {
    if (!commodityId || !region) {
      setMessage({ type: 'error', text: 'Select a commodity and enter a region.' });
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      let config = null;
      try { config = JSON.parse(scrapeConfig); } catch { /* ignore */ }

      await api.post('/api/indexes/sources', {
        team_id: teamId,
        commodity_id: parseInt(commodityId),
        region: region.toUpperCase().trim(),
        source_type: sourceType,
        scrape_url: sourceType === 'scrape_url' ? scrapeUrl : null,
        scrape_config: sourceType === 'scrape_url' ? config : null,
      });
      setMessage({ type: 'success', text: 'Index source added.' });
      // Reset form
      setCommodityId('');
      setRegion('');
      setSourceType('manual');
      setScrapeUrl('');
      setScrapeConfig('{}');
      onAdded();
      setTimeout(() => onClose(), 600);
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to add index.' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Index" width={480}>
      <div className="ca-modal-body">
        <div style={{ marginBottom: 14 }}>
          <label className="ca-label">Commodity</label>
          <select className="ca-select" value={commodityId} onChange={e => setCommodityId(e.target.value)}>
            <option value="">Select commodity...</option>
            {commodities.map(c => (
              <option key={c.id} value={c.id}>
                {c.name}{c.unit ? ` (${c.unit})` : ''}{c.category ? ` [${c.category}]` : ''}
              </option>
            ))}
          </select>
          {commodityId && (() => {
            const sel = commodities.find(c => c.id === parseInt(commodityId));
            return sel?.source_url ? (
              <a href={sel.source_url} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 10, color: 'var(--accent4)', textDecoration: 'underline', marginTop: 4, display: 'inline-block' }}>
                Source: {sel.source_url.length > 60 ? sel.source_url.slice(0, 60) + '...' : sel.source_url}
              </a>
            ) : null;
          })()}
        </div>

        <div style={{ marginBottom: 14 }}>
          <label className="ca-label">Region</label>
          <input
            className="ca-input"
            value={region}
            onChange={e => setRegion(e.target.value)}
            placeholder="e.g. EU, GLOBAL, US, APAC"
          />
        </div>

        <div style={{ marginBottom: 14 }}>
          <label className="ca-label">Source Type</label>
          <select className="ca-select" value={sourceType} onChange={e => setSourceType(e.target.value)}>
            <option value="manual">Manual</option>
            <option value="scrape_url">Scrape URL</option>
            <option value="upload">Upload</option>
          </select>
        </div>

        {sourceType === 'scrape_url' && (
          <>
            <div style={{ marginBottom: 14 }}>
              <label className="ca-label">Scrape URL or IDBANK code</label>
              <input className="ca-input" value={scrapeUrl} onChange={e => setScrapeUrl(e.target.value)} placeholder="https://... or 010002077" />
              {detectedSource && (
                <span className="ca-badge" style={{
                  marginTop: 6, display: 'inline-block',
                  background: 'var(--accent-dim)', color: 'var(--accent)', fontSize: 9,
                }}>
                  Detected: {detectedSource}
                </span>
              )}
            </div>
            {!detectedSource && (
              <div style={{ marginBottom: 14 }}>
                <label className="ca-label">Scrape Config (JSON)</label>
                <textarea
                  className="ca-input"
                  value={scrapeConfig}
                  onChange={e => setScrapeConfig(e.target.value)}
                  rows={3}
                  style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}
                />
              </div>
            )}
          </>
        )}

        {/* Feedback */}
        {message && (
          <div style={{
            padding: '8px 12px', borderRadius: 6, fontSize: 11,
            background: message.type === 'success' ? 'var(--accent-dim)' : 'var(--accent2-dim)',
            color: message.type === 'success' ? 'var(--accent)' : 'var(--accent2)',
          }}>
            {message.text}
          </div>
        )}
      </div>

      <div className="ca-modal-footer">
        <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={onClose}>Cancel</button>
        <button className="ca-btn ca-btn-primary ca-btn-sm" onClick={handleAdd} disabled={saving}>
          {saving ? 'Adding...' : 'Add Index'}
        </button>
      </div>
    </Modal>
  );
}
