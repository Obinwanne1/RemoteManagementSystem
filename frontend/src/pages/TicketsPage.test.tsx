import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import TicketsPage from './TicketsPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('TicketsPage', () => {
  it('renders ticket titles once the API call resolves', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        items: [{
          id: 't1', title: 'Printer offline', priority: 'high', status: 'open',
          sla_breach_at: null, created_at: '2026-01-01T00:00:00Z',
        }],
        total: 1, pages: 1,
      },
    });

    renderWithQueryClient(<TicketsPage />);

    expect(await screen.findByText('Printer offline')).toBeInTheDocument();
  });

  it('shows an empty state when there are no tickets', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0, pages: 0 } });

    renderWithQueryClient(<TicketsPage />);

    await waitFor(() => expect(screen.getByText(/no tickets found/i)).toBeInTheDocument());
  });
});
