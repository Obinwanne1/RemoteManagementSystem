import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import AdminPage from './AdminPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('AdminPage', () => {
  it('renders user rows once the API call resolves', async () => {
    // "items" not "users" — see audits/code_duplication_audit.md Finding N2, a real
    // bug where this component already read data.items from a response the API
    // used to send as "users".
    vi.mocked(api.get).mockResolvedValue({
      data: {
        items: [{
          id: 'u1', email: 'jane@test.local', full_name: 'Jane Smith', role: 'admin',
          mfa_enabled: true, is_active: true, created_at: '2026-01-01T00:00:00Z',
        }],
        total: 1, pages: 1,
      },
    });

    renderWithQueryClient(<AdminPage />);

    expect(await screen.findByText('Jane Smith')).toBeInTheDocument();
    expect(screen.getByText('jane@test.local')).toBeInTheDocument();
  });

  it('shows an empty state when there are no users', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], total: 0, pages: 0 } });

    renderWithQueryClient(<AdminPage />);

    await waitFor(() => expect(screen.getByText(/no users found/i)).toBeInTheDocument());
  });
});
