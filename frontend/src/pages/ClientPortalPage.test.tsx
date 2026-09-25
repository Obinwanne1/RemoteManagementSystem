import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ClientPortalPage from './ClientPortalPage';
import api from '../api/client';
import { AuthProvider } from '../contexts/AuthContext';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

// ClientPortalPage calls useAuth(), which throws outside an AuthProvider, so
// it must be wrapped here (unlike pages with no auth-context dependency).
// AuthProvider reads localStorage.getItem('access_token') on init — leaving
// it unset (as jsdom does by default) keeps `token` null, which is important:
// DashboardPage.test.tsx relies on this same default to avoid ever
// constructing a real `EventSource` (not implemented in jsdom) via useSSE.
function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>{ui}</AuthProvider>
    </QueryClientProvider>
  );
}

describe('ClientPortalPage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders ticket titles once loaded', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        items: [{
          id: 't1', title: 'Printer not working', description: '', status: 'open',
          priority: 'medium', customer_id: 'c1', assignee_id: null,
          created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
          due_date: null, sla_breach_at: null,
        }],
        total: 1, page: 1, per_page: 10, pages: 1,
      },
    });

    renderWithProviders(<ClientPortalPage />);

    expect(await screen.findByText('Printer not working')).toBeInTheDocument();
  });

  it('shows an empty state when there are no tickets', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0, page: 1, per_page: 10, pages: 0 } });

    renderWithProviders(<ClientPortalPage />);

    await waitFor(() => expect(screen.getByText(/no tickets yet/i)).toBeInTheDocument());
  });
});
