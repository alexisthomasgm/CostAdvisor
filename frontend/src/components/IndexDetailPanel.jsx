import { useState, useEffect } from 'react';
import api from '../api';

export default function IndexDetailPanel({ commodity_id, commodity_name, region, teamId, source, globalScraper, onSourceChanged, onRemoved }) {
  const [editing, setEditing] = useState(false);
  const [sourceType, setSourceType] = useState(source?.source_type || 'manual');
  const [scrapeUrl, setScrapeUrl] = useState(source?.scrape_url || '');
  const [scrapeConfig, setScrapeConfig] = useState(
    source?.scrape_config ? JSON.stringify(source.scrape_config, null, 2) : '{}'
  );
  const [saving, setSaving] = useState(false);
  const [scraping, setScraping] = useState(false);
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

  const handleSaveSource = async () => {
    setSaving(true);
    setMessage(null);
    try {
      let config = null;
      try { config = JSON.parse(scrapeConfig); } catch { /* ignore */ }

      const res = await api.post('/api/indexes/sources', {
        team_id: teamId,
        commodity_id,
        region,
        source_type: sourceType,
        scrape_url: sourceType === 'scrape_url' ? scrapeUrl : null,
        scrape_config: sourceType === 'scrape_url' ? config : null,
      });
      onSourceChanged(res.data);
      setEditing(false);
      setMessage({ type: 'success', text: 'Source saved.' });
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to save source.' });
    } finally {
      setSaving(false);
    }
  };

  const handleScrapeNow = async () => {
    if (!source) return;
    setScraping(true);
    setMessage(null);
    try {
      const res = await api.post(`/api/indexes/sources/${source.id}/scrape-now`);
      if (res.data.status === 'ok') {
        const det = res.data.detected_source ? ` (${res.data.detected_source})` : '';
        setMessage({ type: 'success', text: `Scraped value: ${res.data.value}${det}` });
      } else {
        setMessage({ type: 'error', text: `Scrape error: ${res.data.error}` });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Scrape request failed.' });
    } finally {
      setScraping(false);
    }
  };

  const handleResetAll = async () => {
    if (!confirm(`Reset ALL overrides for ${commodity_name} / ${region}? This cannot be undone.`)) return;
    setMessage(null);
    try {
      const res = await api.delete('/api/indexes/overrides/bulk', {
        params: { team_id: teamId, commodity_id, region },
      });
      setMessage({ type: 'success', text: `Deleted ${res.data.count} override(s).` });
      onSourceChanged(source); // trigger refresh
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to reset overrides.' });
    }
  };

  const handleRemove = async () => {
    if (!source) return;
    if (!confirm(`Remove index source for ${commodity_name} / ${region}? This will delete the source configuration.`)) return;
    try {
      await api.delete(`/api/indexes/sources/${source.id}`);
      onRemoved();
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to remove source.' });
    }
  };

  return (
    <div className="idx-detail-panel">
      {/* Global scraper info */}
      {globalScraper && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14,
          padding: '10px 14px', background: 'var(--accent-dim)', borderRadius: 'var(--radius)',
          border: '1px solid rgba(79,255,176,.15)',
        }}>
          <span className="idx-health idx-health-ok" />
          <span style={{ fontSize: 12, color: 'var(--accent)' }}>
            Auto-scraped via <strong>{globalScraper.scraper}</strong>
          </span>
          {globalScraper.scrape_at && (
            <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
              Last updated: {new Date(globalScraper.scrape_at).toLocaleDateString()}
            </span>
          )}
        </div>
      )}

      {/* Team source info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <span className="ca-card-title" style={{ margin: 0 }}>Team Source</span>
        {source ? (
          <>
            <span className="ca-badge" style={{ background: 'var(--accent4-dim)', color: 'var(--accent4)' }}>
              {source.source_type}
            </span>
            {source.scrape_url && (
              <a href={source.scrape_url} target="_blank" rel="noopener noreferrer"
                style={{ fontSize: 11, color: 'var(--accent4)', textDecoration: 'underline' }}>
                {source.scrape_url.length > 50 ? source.scrape_url.slice(0, 50) + '...' : source.scrape_url}
              </a>
            )}
            {source.last_scrape_at && (
              <span style={{ fontSize: 10, color: 'var(--muted)' }}>
                Last: {new Date(source.last_scrape_at).toLocaleDateString()}
              </span>
            )}
          </>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>
            {globalScraper ? 'No team override — using global auto-scraped data' : 'No source configured'}
          </span>
        )}
      </div>

      {/* Edit source form */}
      {editing ? (
        <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 16, marginBottom: 14 }}>
          <div style={{ marginBottom: 10 }}>
            <label className="ca-label">Source Type</label>
            <select className="ca-select" value={sourceType} onChange={e => setSourceType(e.target.value)}>
              <option value="manual">Manual</option>
              <option value="scrape_url">Scrape URL</option>
              <option value="upload">Upload</option>
            </select>
          </div>
          {sourceType === 'scrape_url' && (
            <>
              <div style={{ marginBottom: 10 }}>
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
                <div style={{ marginBottom: 10 }}>
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
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="ca-btn ca-btn-primary ca-btn-sm" onClick={handleSaveSource} disabled={saving}>
              {saving ? 'Saving...' : 'Save Source'}
            </button>
            <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={() => setEditing(true)}>
            {source ? 'Change Source' : 'Configure Source'}
          </button>
          {source?.source_type === 'scrape_url' && (
            <button className="ca-btn ca-btn-ghost ca-btn-sm" onClick={handleScrapeNow} disabled={scraping}>
              {scraping ? 'Scraping...' : 'Re-scrape Now'}
            </button>
          )}
          <button className="ca-btn ca-btn-danger" onClick={handleResetAll}>
            Reset All Overrides
          </button>
          {source && (
            <button className="ca-btn ca-btn-danger" onClick={handleRemove}>
              Remove Index
            </button>
          )}
        </div>
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
  );
}
