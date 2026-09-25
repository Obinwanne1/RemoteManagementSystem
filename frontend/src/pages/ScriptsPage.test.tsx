import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import ScriptsPage from './ScriptsPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function mockGet(scripts: unknown[], runs: unknown[]) {
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url === '/scripts/') return Promise.resolve({ data: scripts });
    if (url === '/devices/') return Promise.resolve({ data: { items: [] } });
    if (url === '/scripts/runs') return Promise.resolve({ data: { items: runs } });
    return Promise.reject(new Error(`unexpected url ${url}`));
  });
}

describe('ScriptsPage', () => {
  it('renders the script library by default', async () => {
    mockGet(
      [{ id: 's1', name: 'Clean Temp Files', shell: 'ps1', is_builtin: true, created_at: '2026-01-01T00:00:00Z' }],
      [],
    );

    renderWithQueryClient(<ScriptsPage />);

    expect(await screen.findByText('Clean Temp Files')).toBeInTheDocument();
    expect(screen.getByText('BUILT-IN')).toBeInTheDocument();
  });

  it('shows run history with an empty state on the Run History tab', async () => {
    mockGet([], []);

    renderWithQueryClient(<ScriptsPage />);
    await userEvent.click(screen.getByRole('button', { name: /run history/i }));

    await waitFor(() => expect(screen.getByText(/no script runs yet/i)).toBeInTheDocument());
  });
});
