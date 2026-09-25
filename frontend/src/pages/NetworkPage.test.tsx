import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import NetworkPage from './NetworkPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('NetworkPage', () => {
  it('renders scan history once loaded', async () => {
    // Only /network/scans is called on initial render — the per-scan detail
    // query is gated by `enabled: !!activeScan`, which starts null.
    vi.mocked(api.get).mockResolvedValue({
      data: { items: [{ id: 's1', subnet: '192.168.1.0/24', status: 'completed', hosts_found: 5, started_at: '2026-01-01T00:00:00Z' }] },
    });

    renderWithQueryClient(<NetworkPage />);

    expect(await screen.findByText('192.168.1.0/24')).toBeInTheDocument();
  });

  it('shows an empty state when no scans have run', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [] } });

    renderWithQueryClient(<NetworkPage />);

    await waitFor(() => expect(screen.getByText(/no scans run yet/i)).toBeInTheDocument());
  });
});
