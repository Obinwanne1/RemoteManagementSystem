import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import DiskManagementPage from './DiskManagementPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const device = {
  id: 'd1', hostname: 'FILE-SRV', display_name: '', platform: 'windows', is_online: true, is_agentless: false,
  latest_metrics: {
    cpu_pct: 10, ram_pct: 20, disk_pct: 80, uptime_seconds: 100, collected_at: '2026-01-01T00:00:00Z',
    disks: [{ mountpoint: 'C:', total_gb: 500, used_gb: 400, free_gb: 100, percent: 80 }],
  },
};

describe('DiskManagementPage', () => {
  it('prompts device selection before showing disk info', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [device] } });

    renderWithQueryClient(<DiskManagementPage />);

    expect(await screen.findByText(/select a device to view disk information/i)).toBeInTheDocument();
  });

  it('shows disk usage cards once a device is selected', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [device] } });

    renderWithQueryClient(<DiskManagementPage />);

    await waitFor(() => expect(screen.getByRole('option', { name: /FILE-SRV/i })).toBeInTheDocument());
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'd1' } });

    expect(await screen.findByText('C:')).toBeInTheDocument();
    expect(screen.getByText('80.0% used')).toBeInTheDocument();
  });
});
