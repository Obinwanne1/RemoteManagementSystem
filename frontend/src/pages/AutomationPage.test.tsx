import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import AutomationPage from './AutomationPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('AutomationPage', () => {
  it('renders profile names once loaded', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/automation/profiles') {
        return Promise.resolve({
          data: { items: [{ id: 'p1', name: 'Nightly Cleanup', trigger_type: 'schedule', is_active: true, run_count: 3, created_at: '2026-01-01T00:00:00Z' }] },
        });
      }
      if (url === '/automation/runs') {
        return Promise.resolve({ data: { items: [] } });
      }
      return Promise.reject(new Error(`unexpected url ${url}`));
    });

    renderWithQueryClient(<AutomationPage />);

    expect(await screen.findByText('Nightly Cleanup')).toBeInTheDocument();
  });

  it('shows an empty state when there are no profiles', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/automation/profiles') return Promise.resolve({ data: { items: [] } });
      if (url === '/automation/runs') return Promise.resolve({ data: { items: [] } });
      return Promise.reject(new Error(`unexpected url ${url}`));
    });

    renderWithQueryClient(<AutomationPage />);

    await waitFor(() => expect(screen.getByText(/no automation profiles configured/i)).toBeInTheDocument());
  });
});
