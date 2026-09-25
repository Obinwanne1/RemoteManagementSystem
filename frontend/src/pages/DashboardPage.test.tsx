import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DashboardPage from './DashboardPage';
import api from '../api/client';
import { AuthProvider } from '../contexts/AuthContext';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

// DashboardPage calls useAuth() (throws outside AuthProvider) and useSSE(token, ...)
// (constructs a real browser EventSource, which jsdom does not implement, when
// `token` is truthy). AuthProvider reads localStorage.getItem('access_token') on
// init; leaving it unset keeps `token` null, so useSSE's connect() returns early
// before ever touching EventSource — no polyfill needed.
function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>{ui}</AuthProvider>
    </QueryClientProvider>
  );
}

describe('DashboardPage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders stat cards from a successful summary fetch', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        devices: { total: 10, online: 8, offline: 2, critical: 1, warning: 1 },
        alerts: { open: 3, critical: 1, acknowledged: 0 },
        tickets: { open: 2, in_progress: 1, overdue: 0 },
      },
    });

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText('Total Devices')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  it('shows an error banner when the summary fetch fails', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('network error'));

    renderWithProviders(<DashboardPage />);

    await waitFor(() => expect(screen.getByText(/failed to load summary/i)).toBeInTheDocument());
  });
});
