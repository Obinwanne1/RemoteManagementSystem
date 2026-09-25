import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import BillingPage from './BillingPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('BillingPage', () => {
  it('renders invoice numbers once loaded', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        items: [{
          id: 'i1', invoice_number: 'INV-2026-0001', customer_id: 'c1', status: 'draft',
          subtotal: 100, tax: 0, total: 100, period_start: '2026-01-01T00:00:00Z',
          period_end: '2026-01-31T00:00:00Z', created_at: '2026-02-01T00:00:00Z',
        }],
        total: 1, pages: 1,
      },
    });

    renderWithQueryClient(<BillingPage />);

    expect(await screen.findByText('INV-2026-0001')).toBeInTheDocument();
  });

  it('shows an empty state when there are no invoices', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0, pages: 0 } });

    renderWithQueryClient(<BillingPage />);

    await waitFor(() => expect(screen.getByText(/no invoices found/i)).toBeInTheDocument());
  });
});
