import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import ReportsPage from './ReportsPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function mockGet(templates: unknown[], reports: unknown[]) {
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url === '/reports/templates') return Promise.resolve({ data: templates });
    if (url === '/reports/') return Promise.resolve({ data: { items: reports } });
    return Promise.reject(new Error(`unexpected url ${url}`));
  });
}

describe('ReportsPage', () => {
  it('renders templates and generated reports once resolved', async () => {
    mockGet(
      [{ id: 't1', name: 'Device Inventory', report_type: 'devices' }],
      [{ id: 'r1', name: 'September Inventory', report_type: 'devices', status: 'completed', created_at: '2026-09-01T00:00:00Z' }],
    );

    renderWithQueryClient(<ReportsPage />);

    expect(await screen.findByText('Device Inventory')).toBeInTheDocument();
    expect(screen.getByText('September Inventory')).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
  });

  it('shows an empty state when there are no generated reports', async () => {
    mockGet([], []);

    renderWithQueryClient(<ReportsPage />);

    await waitFor(() => expect(screen.getByText(/no reports generated yet/i)).toBeInTheDocument());
  });
});
