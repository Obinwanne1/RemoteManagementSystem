import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import AlertsPage from './AlertsPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('AlertsPage', () => {
  it('renders alert messages once the API call resolves', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        items: [{
          id: 'a1', rule_id: 'r1', device_id: 'd1', device_hostname: 'WEB-01',
          severity: 'critical', status: 'open', message: 'CPU at 97%',
          triggered_at: '2026-01-01T00:00:00Z', acknowledged_at: null, resolved_at: null,
        }],
        total: 1, page: 1, pages: 1,
      },
    });

    renderWithQueryClient(<AlertsPage />);

    expect(await screen.findByText('CPU at 97%')).toBeInTheDocument();
    expect(screen.getByText('WEB-01')).toBeInTheDocument();
  });

  it('shows an empty state when there are no alerts', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0, page: 1, pages: 0 } });

    renderWithQueryClient(<AlertsPage />);

    await waitFor(() => expect(screen.getByText(/no open alerts/i)).toBeInTheDocument());
  });
});
