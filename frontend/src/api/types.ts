export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: 'superadmin' | 'admin' | 'technician' | 'viewer' | 'client';
  customer_id: string | null;
  must_change_password: boolean;
  mfa_enabled: boolean;
  avatar_data: string | null;
}

export interface Device {
  id: string;
  hostname: string;
  display_name: string;
  platform: string;
  os_name: string | null;
  os_version: string | null;
  cpu_model: string | null;
  cpu_cores: number | null;
  ram_gb: number | null;
  ip_address: string | null;
  is_online: boolean;
  is_agentless: boolean;
  device_type: string;
  vendor: string | null;
  status: 'healthy' | 'warning' | 'critical' | 'offline' | 'unknown';
  last_seen: string | null;
  customer_id: string | null;
  agent_version: string | null;
  latest_metrics?: DeviceMetrics | null;
}

export interface DeviceMetrics {
  cpu_pct: number | null;
  ram_pct: number | null;
  disk_pct: number | null;
  uptime_seconds: number | null;
  collected_at: string;
}

export interface Alert {
  id: string;
  rule_id: string;
  device_id: string;
  device_hostname?: string;
  severity: 'info' | 'warning' | 'critical';
  status: 'open' | 'acknowledged' | 'resolved';
  message: string;
  triggered_at: string;
  resolved_at: string | null;
}

export interface Ticket {
  id: string;
  title: string;
  description: string;
  status: 'open' | 'in_progress' | 'waiting' | 'resolved' | 'closed';
  priority: 'low' | 'medium' | 'high' | 'critical';
  customer_id: string | null;
  assignee_id: string | null;
  created_at: string;
  updated_at: string;
  due_date: string | null;
  sla_breach_at: string | null;
}

export interface Customer {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  device_count?: number;
  created_at: string;
}

export interface DashboardSummary {
  devices: {
    total: number;
    online: number;
    offline: number;
    critical: number;
    warning: number;
  };
  alerts: {
    open: number;
    critical: number;
    acknowledged: number;
  };
  tickets: {
    open: number;
    in_progress: number;
    overdue: number;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}
