// api.js — all communication with the backend

const API_BASE = 'https://api-dataprep.sofiialutsenko.com';

async function maskFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/api/v1/mask/file`, {
    method: 'POST',
    body: formData,
  });

  if (response.status === 429) {
    throw new Error('Too many requests. Please wait a minute before uploading again.');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `Server error: ${response.status}`);
  }

  return await response.blob();
}