import { useState, useEffect, useRef } from 'react';
import {
  Upload,
  FileCheck,
  AlertCircle,
  Settings,
  Ruler,
  Layers,
  ChevronLeft,
  ChevronRight,
  Eye,
  X,
  FileArchive,
  Sparkles,
} from 'lucide-react';
import {
  checkBackendHealth,
  uploadGeospatialFile,
  getFileInfo,
  getFileMeasurements,
  getApiBaseUrl,
  setApiBaseUrl,
} from './api';
import type {
  FileInfoResponse,
  MeasurementFeatureItem,
  PaginatedMeasurementsResponse,
} from './types';

export function App() {
  // Backend & Connection State
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [apiUrl, setApiUrl] = useState<string>(getApiBaseUrl());
  const [showApiConfig, setShowApiConfig] = useState<boolean>(false);

  // File Upload State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingStep, setLoadingStep] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Results State
  const [currentFileId, setCurrentFileId] = useState<string | null>(null);
  const [fileInfo, setFileInfo] = useState<FileInfoResponse | null>(null);
  const [measurements, setMeasurements] = useState<PaginatedMeasurementsResponse | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Inspector Modal State
  const [inspectFeature, setInspectFeature] = useState<MeasurementFeatureItem | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Check health and url params on mount
  useEffect(() => {
    checkHealth();
    const params = new URLSearchParams(window.location.search);
    const fileIdParam = params.get('file_id');
    if (fileIdParam && fileIdParam !== '1' && fileIdParam.startsWith('geo-')) {
      loadExistingFile(fileIdParam);
    }
  }, []);

  const checkHealth = async () => {
    try {
      await checkBackendHealth();
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    }
  };

  const loadExistingFile = async (id: string) => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      setLoadingStep(`Loading dataset ${id}...`);
      const [info, meas] = await Promise.all([
        getFileInfo(id),
        getFileMeasurements(id, 1, 50),
      ]);
      setCurrentFileId(id);
      setFileInfo(info);
      setMeasurements(meas);
      setCurrentPage(1);
    } catch (err: any) {
      console.warn('Could not load file ID from URL:', err);
    } finally {
      setIsLoading(false);
      setLoadingStep('');
    }
  };

  const loadSampleDataset = async (samplePath: string, sampleFilename: string) => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      setLoadingStep(`Fetching sample file '${sampleFilename}'...`);
      const response = await fetch(samplePath);
      if (!response.ok) {
        throw new Error(`Failed to load ${sampleFilename} from sample library.`);
      }
      const blob = await response.blob();
      const file = new File([blob], sampleFilename, {
        type: sampleFilename.endsWith('.zip') ? 'application/zip' : 'application/vnd.google-earth.kml+xml',
      });
      setSelectedFile(file);

      setLoadingStep('Uploading & projecting geometries to optimal metric CRS...');
      const uploadRes = await uploadGeospatialFile(file);

      setLoadingStep('Retrieving computed measurements...');
      setCurrentFileId(uploadRes.id);

      const [info, meas] = await Promise.all([
        getFileInfo(uploadRes.id),
        getFileMeasurements(uploadRes.id, 1, 50),
      ]);

      setFileInfo(info);
      setMeasurements(meas);
      setCurrentPage(1);
      window.history.pushState({}, '', `?file_id=${uploadRes.id}`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to process sample file.');
    } finally {
      setIsLoading(false);
      setLoadingStep('');
    }
  };

  const handleSaveApiUrl = () => {
    setApiBaseUrl(apiUrl);
    setShowApiConfig(false);
    checkHealth();
  };

  // Drag & Drop Handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    setErrorMessage(null);
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (ext !== 'kml' && ext !== 'zip') {
      setErrorMessage(`Unsupported file format '.${ext}'. Please upload a .kml file or a .zip archive.`);
      return;
    }
    setSelectedFile(file);
  };

  // Upload Submission
  const handleProcessFile = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    setErrorMessage(null);
    setLoadingStep('Uploading archive and verifying components...');

    try {
      setLoadingStep('Checking Coordinate Reference System & projecting geometries...');
      const uploadRes = await uploadGeospatialFile(selectedFile);

      setLoadingStep('Fetching stored calculations...');
      setCurrentFileId(uploadRes.id);

      const [info, meas] = await Promise.all([
        getFileInfo(uploadRes.id),
        getFileMeasurements(uploadRes.id, 1, 50),
      ]);

      setFileInfo(info);
      setMeasurements(meas);
      setCurrentPage(1);
    } catch (err: any) {
      setErrorMessage(err.message || 'An unexpected error occurred during processing.');
    } finally {
      setIsLoading(false);
      setLoadingStep('');
    }
  };

  // Fetch page change
  const handlePageChange = async (newPage: number) => {
    if (!currentFileId || !measurements) return;
    if (newPage < 1 || newPage > measurements.pages) return;

    try {
      setIsLoading(true);
      const meas = await getFileMeasurements(currentFileId, newPage, 50);
      setMeasurements(meas);
      setCurrentPage(newPage);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Filter features
  const filteredItems = (measurements?.items || []).filter((item) => {
    if (filterType !== 'all') {
      const gType = item.geometry_type.toLowerCase();
      if (filterType === 'polygon' && !gType.includes('polygon')) return false;
      if (filterType === 'line' && !gType.includes('line')) return false;
      if (filterType === 'point' && !gType.includes('point')) return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const propsStr = JSON.stringify(item.properties).toLowerCase();
      return propsStr.includes(q) || item.geometry_type.toLowerCase().includes(q);
    }
    return true;
  });

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <div className="brand-section">
            <div className="brand-icon">
              <Layers size={18} />
            </div>
            <div>
              <div className="brand-title">GeoMeasure</div>
              <div className="brand-subtitle">Geospatial File Measurement & Verification</div>
            </div>
          </div>

          <div className="header-actions">
            <div
              className={`status-badge ${backendOnline === true ? 'online' : backendOnline === false ? 'offline' : ''}`}
              title={backendOnline ? 'Backend connected' : 'Backend offline'}
            >
              <div className="status-dot" />
              <span>{backendOnline ? 'Backend Online' : 'Backend Offline'}</span>
            </div>

            <button
              className="btn-icon-subtle"
              onClick={() => setShowApiConfig(!showApiConfig)}
              title="Configure API Base URL"
            >
              <Settings size={14} />
              <span>API URL</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="main-content">
        {/* API URL Config Box */}
        {showApiConfig && (
          <div className="api-config-box">
            <div className="api-config-input-group">
              <span style={{ fontWeight: 600 }}>API Base URL:</span>
              <input
                type="text"
                className="api-input"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://localhost:8000"
              />
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn-primary" onClick={handleSaveApiUrl}>
                Save & Connect
              </button>
              <button className="btn-secondary" onClick={() => setShowApiConfig(false)}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Intro */}
        <section className="page-intro">
          <h1 className="page-title">Geospatial Processing & Measurements</h1>
          <p className="page-description">
            Upload KML or complete zipped Shapefiles. GeoMeasure securely inspects archive integrity, enforces
            CRS validation, reprojects geometries to an optimal local metric projection, and computes exact area and length.
          </p>
        </section>

        {/* Upload Card */}
        <section className="upload-card">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".kml,.zip"
            style={{ display: 'none' }}
          />

          <div
            className={`dropzone ${isDragging ? 'active' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload size={32} className="dropzone-icon" />
            <div className="dropzone-title">Click to browse or drop geospatial file here</div>
            <div className="dropzone-subtitle">Supported formats: Single .kml file or .zip Shapefile archive</div>
            <div className="file-specs">
              <span className="spec-tag">.kml (WGS84)</span>
              <span className="spec-tag">.zip (.shp, .shx, .dbf, .prj)</span>
              <span>Max 50 MB</span>
            </div>
          </div>

          {/* Quick Try Sample Datasets */}
          <div className="samples-toolbar">
            <div className="samples-toolbar-header">
              <Sparkles size={16} color="var(--navy-primary)" />
              <span className="samples-toolbar-title">Try Live Sample Datasets (1-Click Measure):</span>
            </div>
            <div className="samples-btn-group">
              <button
                type="button"
                className="btn-sample"
                disabled={isLoading}
                onClick={() => loadSampleDataset('/samples/new_york_central_park.kml', 'new_york_central_park.kml')}
                title="Central Park perimeter polygon, reservoir track line, and Bethesda Terrace point"
              >
                <span>Central Park NYC</span>
                <span className="badge-kml">KML</span>
              </button>
              <button
                type="button"
                className="btn-sample"
                disabled={isLoading}
                onClick={() => loadSampleDataset('/samples/taj_mahal_heritage.kml', 'taj_mahal_heritage.kml')}
                title="Taj Mahal Charbagh complex polygon, Yamuna riverfront line, and dome point"
              >
                <span>Taj Mahal Complex</span>
                <span className="badge-kml">KML</span>
              </button>
              <button
                type="button"
                className="btn-sample"
                disabled={isLoading}
                onClick={() => loadSampleDataset('/samples/paris_gardens_shapefile.zip', 'paris_gardens_shapefile.zip')}
                title="Paris Champ de Mars, Trocadéro, and Invalides parcel shapefiles"
              >
                <span>Paris Gardens Parcels</span>
                <span className="badge-zip">Shapefile ZIP</span>
              </button>
            </div>
          </div>

          {selectedFile && (
            <div className="selected-file-box">
              <div className="file-info-group">
                <FileCheck size={20} color="var(--green-main)" />
                <div>
                  <div className="file-name">{selectedFile.name}</div>
                  <div className="file-size">{formatFileSize(selectedFile.size)}</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn-secondary" onClick={() => setSelectedFile(null)}>
                  Clear
                </button>
                <button
                  className="btn-primary"
                  onClick={handleProcessFile}
                  disabled={isLoading}
                >
                  <Ruler size={14} />
                  <span>Process & Measure</span>
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Error Alert Box */}
        {errorMessage && (
          <section className="error-box">
            <AlertCircle size={20} className="error-icon" />
            <div style={{ flex: 1 }}>
              <div className="error-title">Processing Error</div>
              <div className="error-message">{errorMessage}</div>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--red-main)' }}
            >
              <X size={16} />
            </button>
          </section>
        )}

        {/* Loading State */}
        {isLoading && (
          <section className="loading-box">
            <div className="spinner" />
            <div className="loading-title">Processing Geospatial File</div>
            <div className="loading-steps">{loadingStep || 'Analyzing geometries...'}</div>
          </section>
        )}

        {/* Results View */}
        {!isLoading && fileInfo && (
          <section className="results-card">
            {/* Header / Summary */}
            <div className="results-header">
              <div className="results-header-top">
                <div className="results-filename">
                  <FileCheck size={22} color="var(--green-main)" />
                  <span>{fileInfo.filename}</span>
                  <span className="status-tag completed">{fileInfo.status}</span>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    ID: <code>{fileInfo.id}</code>
                  </span>
                </div>
              </div>

              {/* Metadata Grid */}
              <div className="metadata-grid">
                <div className="meta-item">
                  <span className="meta-label">Features Count</span>
                  <span className="meta-value">{fileInfo.feature_count}</span>
                  <span className="meta-subtext">{fileInfo.file_type.toUpperCase()} dataset</span>
                </div>

                <div className="meta-item">
                  <span className="meta-label">Source CRS</span>
                  <span className="meta-value">{fileInfo.source_crs}</span>
                  <span className="meta-subtext">Original coordinate system</span>
                </div>

                <div className="meta-item">
                  <span className="meta-label">Measurement Projected CRS</span>
                  <span className="meta-value">{fileInfo.measurement_crs || 'N/A'}</span>
                  <span className="meta-subtext">{fileInfo.projection_method || 'Metric Projection'}</span>
                </div>

                {fileInfo.summary_measurements?.total_area_m2 && (
                  <div className="meta-item">
                    <span className="meta-label">Total Polygon Area</span>
                    <span className="meta-value">
                      {fileInfo.summary_measurements.total_area_m2.toLocaleString()} m²
                    </span>
                    <span className="meta-subtext">
                      ({fileInfo.summary_measurements.total_area_km2?.toFixed(4)} km²)
                    </span>
                  </div>
                )}

                {fileInfo.summary_measurements?.total_length_m && (
                  <div className="meta-item">
                    <span className="meta-label">Total Line Length</span>
                    <span className="meta-value">
                      {fileInfo.summary_measurements.total_length_m.toLocaleString()} m
                    </span>
                    <span className="meta-subtext">
                      ({fileInfo.summary_measurements.total_length_km?.toFixed(3)} km)
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Table Filter Toolbar */}
            <div className="table-toolbar">
              <div className="filter-group">
                <button
                  className={`filter-btn ${filterType === 'all' ? 'active' : ''}`}
                  onClick={() => setFilterType('all')}
                >
                  All Features ({measurements?.total || 0})
                </button>
                <button
                  className={`filter-btn ${filterType === 'polygon' ? 'active' : ''}`}
                  onClick={() => setFilterType('polygon')}
                >
                  Polygons
                </button>
                <button
                  className={`filter-btn ${filterType === 'line' ? 'active' : ''}`}
                  onClick={() => setFilterType('line')}
                >
                  Lines
                </button>
                <button
                  className={`filter-btn ${filterType === 'point' ? 'active' : ''}`}
                  onClick={() => setFilterType('point')}
                >
                  Points
                </button>
              </div>

              <input
                type="text"
                className="search-input"
                placeholder="Search properties or type..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Feature Measurements Table */}
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '60px' }}>#</th>
                    <th>Geometry Type</th>
                    <th>Metric Measurement</th>
                    <th>Unit</th>
                    <th>Calculation Status</th>
                    <th style={{ textAlign: 'right' }}>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredItems.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-light)' }}>
                        No features match your current filter.
                      </td>
                    </tr>
                  ) : (
                    filteredItems.map((item) => {
                      const m = item.measurement;
                      const gType = item.geometry_type.toLowerCase();
                      const badgeClass = gType.includes('poly')
                        ? 'polygon'
                        : gType.includes('line')
                        ? 'line'
                        : 'point';

                      // Format display measurement
                      let measurementDisplay = '—';
                      if (m.area_m2 !== null) {
                        measurementDisplay = `${m.area_m2.toLocaleString()} m² (${m.area_km2?.toFixed(4)} km²)`;
                      } else if (m.length_m !== null) {
                        measurementDisplay = `${m.length_m.toLocaleString()} m (${m.length_km?.toFixed(3)} km)`;
                      } else if (m.notes) {
                        measurementDisplay = m.notes;
                      }

                      return (
                        <tr key={item.feature_index}>
                          <td style={{ fontWeight: 600, color: 'var(--text-light)' }}>
                            {item.feature_index}
                          </td>
                          <td>
                            <span className={`badge-pill ${badgeClass}`}>
                              {item.geometry_type}
                            </span>
                          </td>
                          <td className="metric-cell" style={{ fontSize: '0.84rem' }}>
                            {measurementDisplay}
                          </td>
                          <td style={{ color: 'var(--text-muted)' }}>
                            {m.unit || '—'}
                          </td>
                          <td>
                            <span className={`status-tag ${m.status.toLowerCase()}`}>
                              {m.status}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              className="btn-icon-subtle"
                              onClick={() => setInspectFeature(item)}
                              title="Inspect properties and coordinates"
                            >
                              <Eye size={13} />
                              <span>Inspect</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {measurements && measurements.pages > 1 && (
              <div className="table-pagination">
                <div>
                  Showing page {measurements.page} of {measurements.pages} ({measurements.total} total features)
                </div>

                <div className="pagination-controls">
                  <button
                    className="btn-secondary"
                    disabled={currentPage <= 1}
                    onClick={() => handlePageChange(currentPage - 1)}
                  >
                    <ChevronLeft size={14} />
                    <span>Previous</span>
                  </button>

                  <span style={{ padding: '0 0.5rem', fontWeight: 500 }}>
                    {currentPage} / {measurements.pages}
                  </span>

                  <button
                    className="btn-secondary"
                    disabled={currentPage >= measurements.pages}
                    onClick={() => handlePageChange(currentPage + 1)}
                  >
                    <span>Next</span>
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Empty State */}
        {!isLoading && !fileInfo && (
          <section className="empty-state">
            <Ruler size={36} className="empty-icon" />
            <h2 className="empty-title">No Geospatial Dataset Loaded</h2>
            <p className="empty-text">
              Select or drop a valid file above to begin validation and metric measurements.
            </p>

            <div className="guide-cards">
              <div className="guide-card">
                <div className="guide-card-title">
                  <FileCheck size={16} color="var(--green-main)" />
                  <span>KML Documents (.kml)</span>
                </div>
                <div className="guide-card-desc">
                  Standard OGC KML files containing Placemarks with Polygons, LineStrings, or Points in WGS84.
                </div>
              </div>

              <div className="guide-card">
                <div className="guide-card-title">
                  <FileArchive size={16} color="var(--navy-primary)" />
                  <span>Zipped Shapefiles (.zip)</span>
                </div>
                <div className="guide-card-desc">
                  Archive must contain the complete Shapefile bundle: <code>.shp</code> (geometry), <code>.shx</code> (index), <code>.dbf</code> (attributes), and <code>.prj</code> (CRS).
                </div>
              </div>
            </div>
          </section>
        )}
      </main>

      {/* Feature Inspector Modal */}
      {inspectFeature && (
        <div className="modal-backdrop" onClick={() => setInspectFeature(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                Feature #{inspectFeature.feature_index} — {inspectFeature.geometry_type}
              </div>
              <button
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                onClick={() => setInspectFeature(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {/* Properties */}
              <div>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem' }}>Feature Attributes</h4>
                {Object.keys(inspectFeature.properties).length === 0 ? (
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-light)' }}>No attributes recorded for this feature.</div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                    <tbody>
                      {Object.entries(inspectFeature.properties).map(([k, v]) => (
                        <tr key={k} style={{ borderBottom: '1px solid var(--border-color)' }}>
                          <td style={{ padding: '0.35rem 0.5rem', fontWeight: 600, color: 'var(--text-muted)', width: '35%' }}>
                            {k}
                          </td>
                          <td style={{ padding: '0.35rem 0.5rem', fontFamily: 'var(--font-mono)' }}>
                            {v !== null ? String(v) : '<null>'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Measurement Details */}
              <div>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem' }}>Computed Measurements</h4>
                <div style={{ background: 'var(--bg-app)', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '0.75rem', fontSize: '0.82rem' }}>
                  <div><strong>Status:</strong> {inspectFeature.measurement.status}</div>
                  {inspectFeature.measurement.area_m2 !== null && (
                    <>
                      <div><strong>Area (m²):</strong> {inspectFeature.measurement.area_m2.toLocaleString()} m²</div>
                      <div><strong>Area (km²):</strong> {inspectFeature.measurement.area_km2?.toFixed(6)} km²</div>
                    </>
                  )}
                  {inspectFeature.measurement.length_m !== null && (
                    <>
                      <div><strong>Length (m):</strong> {inspectFeature.measurement.length_m.toLocaleString()} m</div>
                      <div><strong>Length (km):</strong> {inspectFeature.measurement.length_km?.toFixed(5)} km</div>
                    </>
                  )}
                  {inspectFeature.measurement.notes && (
                    <div style={{ marginTop: '0.25rem', color: 'var(--text-muted)' }}>
                      <strong>Notes:</strong> {inspectFeature.measurement.notes}
                    </div>
                  )}
                </div>
              </div>

              {/* GeoJSON Geometry Preview */}
              <div>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem' }}>GeoJSON Geometry</h4>
                <pre className="json-preview">
                  {JSON.stringify(inspectFeature.geometry, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
