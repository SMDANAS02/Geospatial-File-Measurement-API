import type {
  FileInfoResponse,
  FileUploadResponse,
  HealthResponse,
  PaginatedMeasurementsResponse,
} from './types';

// Configurable backend API base URL with fallback to local development server
export const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  const custom = localStorage.getItem('geomeasure_api_url');
  if (custom && custom.trim()) {
    return custom.trim().replace(/\/+$/, '');
  }
  return 'http://localhost:8000';
};

export const setApiBaseUrl = (url: string): void => {
  if (url && url.trim()) {
    localStorage.setItem('geomeasure_api_url', url.trim().replace(/\/+$/, ''));
  } else {
    localStorage.removeItem('geomeasure_api_url');
  }
};

export async function checkBackendHealth(): Promise<HealthResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/health`);
  if (!res.ok) {
    throw new Error(`Backend health check failed (${res.status} ${res.statusText})`);
  }
  return res.json();
}

export async function uploadGeospatialFile(file: File): Promise<FileUploadResponse> {
  const base = getApiBaseUrl();
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${base}/api/files/`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    let errorMessage = `Upload failed with HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errorMessage = errJson.detail;
      }
    } catch {
      // Fallback to text
      const errText = await res.text();
      if (errText) errorMessage = errText;
    }
    throw new Error(errorMessage);
  }

  return res.json();
}

export async function getFileInfo(fileId: string): Promise<FileInfoResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/api/files/${fileId}/`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to retrieve file info' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getFileMeasurements(
  fileId: string,
  page = 1,
  pageSize = 50
): Promise<PaginatedMeasurementsResponse> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/api/files/${fileId}/measurements/?page=${page}&page_size=${pageSize}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to retrieve measurements' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
