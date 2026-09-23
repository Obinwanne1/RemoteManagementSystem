import api from './client';

export interface UsageServiceStat {
  service: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  error_count: number;
  error_rate: number;
}

export interface UsageAnomaly {
  service: string;
  current_hour_count: number;
  baseline_avg: number;
  multiplier: number;
}

export interface UsageSummary {
  range: string;
  services: UsageServiceStat[];
  totals: {
    calls: number;
    tokens: number;
    estimated_cost_usd: number;
    error_count: number;
    error_rate: number;
  };
  anomalies: UsageAnomaly[];
}

export interface UsageTimeseriesPoint { bucket: string; value: number }

export interface UsageTimeseries {
  range: string;
  service: string | null;
  metric: string;
  points: UsageTimeseriesPoint[];
}

export interface UsageByFeatureItem {
  service: string;
  feature: string | null;
  user_id: string | null;
  user_email: string | null;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
}

export interface UsageEvent {
  id: number;
  service: string;
  feature: string | null;
  user_id: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  status: string;
  status_code: number | null;
  latency_ms: number | null;
  error_message: string | null;
  created_at: string | null;
}

export interface UsageAlertConfig {
  is_enabled: boolean;
  spike_multiplier: number;
  notification_channels: { email?: string[]; slack?: string[]; teams?: string[]; webhook?: string[] };
  updated_at: string | null;
  updated_by: string | null;
}

export function getUsageSummary(range = '7d') {
  return api.get<UsageSummary>('/admin/usage/summary', { params: { range } }).then((r) => r.data);
}

export function getUsageTimeseries(range = '7d', metric = 'calls', service?: string) {
  return api.get<UsageTimeseries>('/admin/usage/timeseries', { params: { range, metric, service } })
    .then((r) => r.data);
}

export function getUsageByFeature(range = '7d', service?: string) {
  return api.get<{ range: string; items: UsageByFeatureItem[] }>('/admin/usage/by-feature', {
    params: { range, service },
  }).then((r) => r.data);
}

export function getUsageEvents(params: { service?: string; status?: string; page?: number; per_page?: number } = {}) {
  return api.get<{ items: UsageEvent[]; total: number; page: number; per_page: number }>(
    '/admin/usage/events', { params },
  ).then((r) => r.data);
}

export function getUsageAlertConfig() {
  return api.get<UsageAlertConfig>('/admin/usage/alert-config').then((r) => r.data);
}

export function updateUsageAlertConfig(config: Partial<UsageAlertConfig>) {
  return api.put<UsageAlertConfig>('/admin/usage/alert-config', config).then((r) => r.data);
}
