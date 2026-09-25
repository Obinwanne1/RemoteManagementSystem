import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import CustomersPage from './CustomersPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('CustomersPage', () => {
  it('renders customer names once the API call resolves', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { items: [{ id: '1', name: 'Acme Corp', is_active: true, created_at: '2026-01-01T00:00:00Z' }], total: 1, pages: 1 },
    });

    renderWithQueryClient(<CustomersPage />);

    expect(await screen.findByText('Acme Corp')).toBeInTheDocument();
  });

  it('shows an empty state when there are no customers', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0, pages: 0 } });

    renderWithQueryClient(<CustomersPage />);

    await waitFor(() => expect(screen.getByText(/no customers/i)).toBeInTheDocument());
  });
});
