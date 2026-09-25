import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import DevicesPage from './DevicesPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('DevicesPage', () => {
  it('renders device hostnames once the API call resolves', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        items: [
          {
            id: 'd1', hostname: 'WEB-SERVER-01', display_name: '', platform: 'windows',
            os_name: 'Windows Server 2022', os_version: null, cpu_model: null, cpu_cores: null,
            ram_gb: null, ip_address: '10.0.0.5', is_online: true, is_agentless: false,
            device_type: 'server', vendor: null, status: 'healthy', last_seen: '2026-01-01T00:00:00Z',
            customer_id: 'c1', agent_version: '1.0.0', latest_metrics: null,
          },
        ],
        total: 1, page: 1, pages: 1,
      },
    });

    renderWithQueryClient(<DevicesPage />);

    expect(await screen.findByText('WEB-SERVER-01')).toBeInTheDocument();
    expect(screen.getByText('healthy')).toBeInTheDocument();
  });

  it('shows an empty state when there are no devices', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0, page: 1, pages: 0 } });

    renderWithQueryClient(<DevicesPage />);

    await waitFor(() => expect(screen.getByText(/no devices found/i)).toBeInTheDocument());
  });
});
