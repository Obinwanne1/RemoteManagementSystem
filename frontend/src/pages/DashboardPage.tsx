import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Monitor, Wifi, AlertTriangle, Bell, Ticket, RefreshCw, Radio } from 'lucide-react';
import { useState, useCallback } from 'react';
import api from '../api/client';
import type { DashboardSummary } from '../api/types';
import StatCard from '../components/StatCard';
import { useAuth } from '../contexts/AuthContext';
import { useSSE } from '../hooks/useSSE';

const LIVE_EVENTS = new Set([
  'alert_fired', 'alert_resolved', 'device_online', 'device_offline',
  'ticket_created', 'ticket_closed', 'heartbeat',
]);

function fetchSummary(): Promise<DashboardSummary> {
  return api.get('/dashboard/summary').then((r) => r.data);
}

export default function DashboardPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [liveConnected, setLiveConnected] = useState(false);

  const handleSSEMessage = useCallback((type: string) => {
    if (LIVE_EVENTS.has(type)) {
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] });
    }
  }, [queryClient]);

  useSSE(token, {
    onConnect: () => setLiveConnected(true),
    onError: () => setLiveConnected(false),
    onMessage: handleSSEMessage,
  });

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: fetchSummary,
    refetchInterval: 60_000, // fallback poll every 60s; SSE triggers faster updates
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Overview</h1>
          <p className="text-sm text-gray-500">Live system status</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-1.5 text-xs font-medium ${liveConnected ? 'text-green-600' : 'text-gray-400'}`}>
            <Radio size={13} className={liveConnected ? 'animate-pulse' : ''} />
            {liveConnected ? 'Live' : 'Polling'}
          </span>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-brand-600 transition disabled:opacity-50"
          >
            <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {isError && (
        <div className="bg-red-50 border border-red-100 text-red-700 text-sm px-4 py-3 rounded-lg">
          Failed to load summary. Check API connection.
        </div>
      )}

      {/* Stat cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 p-5 h-24 animate-pulse" />
          ))}
        </div>
      ) : data ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard
            title="Total Devices"
            value={data.devices.total}
            icon={<Monitor size={20} />}
          />
          <StatCard
            title="Online"
            value={data.devices.online}
            sub={`${data.devices.offline} offline`}
            icon={<Wifi size={20} />}
            color="green"
          />
          <StatCard
            title="Critical"
            value={data.devices.critical}
            sub={data.devices.critical > 0 ? 'needs attention' : 'all clear'}
            icon={<AlertTriangle size={20} />}
            color={data.devices.critical > 0 ? 'red' : 'green'}
          />
          <StatCard
            title="Open Alerts"
            value={data.alerts.open}
            sub={`${data.alerts.critical} critical`}
            icon={<Bell size={20} />}
            color={data.alerts.open > 0 ? 'yellow' : 'green'}
          />
          <StatCard
            title="Open Tickets"
            value={data.tickets.open}
            sub={data.tickets.overdue > 0 ? `${data.tickets.overdue} overdue` : undefined}
            icon={<Ticket size={20} />}
            color={data.tickets.overdue > 0 ? 'red' : 'default'}
          />
        </div>
      ) : null}

      {/* Status strip */}
      {data && (
        <div className="bg-brand-50 border border-brand-100 rounded-xl px-5 py-4 text-sm text-brand-700">
          <span className="font-semibold">System status: </span>
          {data.devices.offline === 0 && data.alerts.open === 0
            ? '✓ All devices online, no open alerts.'
            : `${data.devices.offline} device(s) offline · ${data.alerts.open} open alert(s).`}
        </div>
      )}
    </div>
  );
}
