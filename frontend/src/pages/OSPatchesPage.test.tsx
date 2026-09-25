import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import OSPatchesPage from './OSPatchesPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('OSPatchesPage', () => {
  it('renders patch titles once loaded', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/patches/summary') {
        return Promise.resolve({ data: { total_pending: 1, total_installed: 0, total_failed: 0, by_device: [] } });
      }
      if (url === '/patches/') {
        return Promise.resolve({
          data: {
            items: [{
              id: 'p1', device_id: 'd1', patch_id: 'kb1', title: 'Security Update KB123456',
              severity: 'critical', status: 'pending', discovered_at: '2026-01-01T00:00:00Z',
            }],
            total: 1, pages: 1, page: 1, per_page: 20,
          },
        });
      }
      return Promise.reject(new Error(`unexpected url ${url}`));
    });

    renderWithQueryClient(<OSPatchesPage />);

    expect(await screen.findByText('Security Update KB123456')).toBeInTheDocument();
  });

  it('shows an empty state when there are no pending patches', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/patches/summary') {
        return Promise.resolve({ data: { total_pending: 0, total_installed: 0, total_failed: 0, by_device: [] } });
      }
      if (url === '/patches/') {
        return Promise.resolve({ data: { items: [], total: 0, pages: 0, page: 1, per_page: 20 } });
      }
      return Promise.reject(new Error(`unexpected url ${url}`));
    });

    renderWithQueryClient(<OSPatchesPage />);

    await waitFor(() => expect(screen.getByText(/no pending patches/i)).toBeInTheDocument());
  });
});
