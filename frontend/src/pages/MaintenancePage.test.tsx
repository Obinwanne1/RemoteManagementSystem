import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import MaintenancePage from './MaintenancePage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const onlineDevice = {
  id: 'd1', hostname: 'DESKTOP-01', display_name: '', platform: 'windows', os_name: 'Windows 11',
  ip_address: '10.0.0.9', is_online: true, is_agentless: false, latest_metrics: { cpu_pct: 5, ram_pct: 40, uptime_seconds: 3661 },
};
const offlineDevice = { ...onlineDevice, id: 'd2', hostname: 'OFFLINE-PC', is_online: false };

describe('MaintenancePage', () => {
  it('prompts device selection before showing actions', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [onlineDevice] } });

    renderWithQueryClient(<MaintenancePage />);

    expect(await screen.findByText(/select an online device to perform maintenance/i)).toBeInTheDocument();
  });

  it('excludes offline devices from the selector', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [onlineDevice, offlineDevice] } });

    renderWithQueryClient(<MaintenancePage />);

    await waitFor(() => expect(screen.getByRole('option', { name: /DESKTOP-01/i })).toBeInTheDocument());
    expect(screen.queryByRole('option', { name: /OFFLINE-PC/i })).not.toBeInTheDocument();
  });

  it('shows the maintenance action grid once a device is selected', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [onlineDevice] } });

    renderWithQueryClient(<MaintenancePage />);

    await waitFor(() => expect(screen.getByRole('option', { name: /DESKTOP-01/i })).toBeInTheDocument());
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'd1' } });

    expect(await screen.findByText('Clean Temp Files')).toBeInTheDocument();
    expect(screen.getByText('Shutdown Device')).toBeInTheDocument();
  });
});
