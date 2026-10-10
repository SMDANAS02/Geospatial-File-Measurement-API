export interface HealthResponse {
  status: string;
  app_name: string;
  environment: string;
  version: string;
  database_status: string;
}

export interface FileUploadResponse {
  id: string;
  filename: string;
  feature_count: number;
  crs: string;
  measurement_crs: string | null;
  status: string;
}

export interface SummaryMeasurements {
  total_features: number;
  measured_polygons: number;
  total_area_m2: number | null;
  total_area_km2: number | null;
  measured_lines: number;
  total_length_m: number | null;
  total_length_km: number | null;
}

export interface FileInfoResponse {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  feature_count: number;
  crs: string;
  source_crs: string;
  measurement_crs: string | null;
  projection_method: string | null;
  status: string;
  created_at: string;
  summary_measurements: SummaryMeasurements | null;
}

export interface StoredMeasurementDetail {
  status: string;
  area_m2: number | null;
  area_km2: number | null;
  length_m: number | null;
  length_km: number | null;
  unit: string | null;
  notes: string | null;
}

export interface MeasurementFeatureItem {
  feature_index: number;
  geometry_type: string;
  geometry: Record<string, any> | null;
  properties: Record<string, any>;
  measurement: StoredMeasurementDetail;
}

export interface PaginatedMeasurementsResponse {
  file_id: string;
  filename: string;
  total: number;
  page: number;
  page_size: number;
  pages: number;
  items: MeasurementFeatureItem[];
}
