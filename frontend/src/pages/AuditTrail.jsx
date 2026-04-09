import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function AuditTrail() {
  const { activeTeamId } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [entityType, setEntityType] = useState('');
  const PAGE_SIZE = 50;

  const fetchLogs = (reset = false) => {
    if (!activeTeamId) return;
    const p = reset ? 0 : page;
    if (reset) setPage(0);
    setLoading(true);
    const params = { team_id: activeTeamId, skip: p * PAGE_SIZE, limit: PAGE_SIZE };
    if (entityType) params.entity_type = entityType;
    api.get('/api/audit', { params })
      .then(res => {
        const rows = res.data;
        if (reset) setLogs(rows);
        else setLogs(prev => [...prev, ...rows]);
        setHasMore(rows.length === PAGE_SIZE);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchLogs(true); }, [activeTeamId, entityType]);

  const loadMore = () => {
    setPage(p => p + 1);
  };

  useEffect(() => {
    if (page > 0) fetchLogs();
  }, [page]);

  const formatDate = (iso) => {
    if (!iso) return '\u2014';
    const d = new Date(iso);
    return d.toLocaleString();
  };

  return (
    <div className="ca-page ca-fade-in">
      <div className="ca-h1" style={{ marginBottom: 4 }}>Audit Trail</div>
      <p className="ca-subtitle">All changes made by your team.</p>

      <div className="ca-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
          <div>
            <label className="ca-label">Entity Type</label>
            <select className="ca-select" value={entityType} onChange={e => setEntityType(e.target.value)}>
              <option value="">All</option>
              <option value="cost_model">Cost Model</option>
              <option value="formula_version">Formula Version</option>
              <option value="price_data">Price Data</option>
              <option value="actual_volume">Volume</option>
              <option value="supplier">Supplier</option>
              <option value="product">Product</option>
              <option value="index_override">Index Override</option>
            </select>
          </div>
        </div>
      </div>

      {loading && logs.length === 0 ? (
        <div style={{ padding: 20, color: 'var(--muted)' }}>Loading...</div>
      ) : logs.length === 0 ? (
        <div className="ca-card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>
          No audit events found.
        </div>
      ) : (
        <div className="ca-card">
          <div className="ca-scroll-x">
            <table className="ca-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Event</th>
                  <th>Entity</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id}>
                    <td style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
                      {formatDate(log.created_at)}
                    </td>
                    <td style={{ fontSize: 11 }}>{log.user_email || '\u2014'}</td>
                    <td>
                      <span style={{
                        display: 'inline-block', padding: '1px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                        background: log.event_type === 'create' ? 'rgba(79,255,176,.12)' : log.event_type === 'delete' ? 'rgba(232,65,24,.15)' : 'rgba(116,185,255,.15)',
                        color: log.event_type === 'create' ? 'var(--accent)' : log.event_type === 'delete' ? 'var(--accent2)' : 'var(--accent3)',
                      }}>
                        {log.event_type}
                      </span>
                    </td>
                    <td style={{ fontSize: 11 }}>
                      <span style={{ color: 'var(--text)' }}>{log.entity_type}</span>
                      <span style={{ color: 'var(--muted)', marginLeft: 6, fontSize: 9 }}>{log.entity_id?.slice(0, 8)}</span>
                    </td>
                    <td style={{ maxWidth: 300 }}>
                      {log.new_value ? (
                        <details style={{ fontSize: 10 }}>
                          <summary style={{ cursor: 'pointer', color: 'var(--accent3)' }}>View changes</summary>
                          <pre style={{ marginTop: 4, padding: 8, background: 'var(--surface2)', borderRadius: 4, overflow: 'auto', maxHeight: 150, fontSize: 9 }}>
                            {JSON.stringify(log.new_value, null, 2)}
                          </pre>
                        </details>
                      ) : '\u2014'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div style={{ textAlign: 'center', marginTop: 12 }}>
              <button className="ca-btn ca-btn-ghost" onClick={loadMore} disabled={loading}>
                {loading ? 'Loading...' : 'Load More'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
