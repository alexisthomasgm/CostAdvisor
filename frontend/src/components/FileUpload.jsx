import { useState, useRef } from 'react';
import api from '../api';

export default function FileUpload({ endpoint, onSuccess, accept = '.csv,.xlsx,.xls' }) {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const { data } = await api.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(data);
      if (onSuccess) onSuccess(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div>
      <input
        ref={fileRef}
        type="file"
        accept={accept}
        onChange={handleUpload}
        style={{ display: 'none' }}
      />
      <button
        className="ca-btn ca-btn-ghost ca-btn-sm"
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
      >
        {uploading ? 'Uploading...' : 'Upload File'}
      </button>
      {result && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--accent)' }}>
          {result.rows_processed} rows processed from {result.filename}
        </div>
      )}
      {error && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--accent2)' }}>
          {error}
        </div>
      )}
    </div>
  );
}