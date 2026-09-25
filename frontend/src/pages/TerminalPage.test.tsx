import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import TerminalPage from './TerminalPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('TerminalPage', () => {
  // No session is opened in these tests, so the 2s output-polling query
  // (enabled: !!session?.sessionId) never activates — no fake timers needed.
  it('lists only online, non-agentless devices in the target picker', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        items: [
          { id: 'd1', hostname: 'ONLINE-PC', is_online: true, is_agentless: false },
          { id: 'd2', hostname: 'OFFLINE-PC', is_online: false, is_agentless: false },
          { id: 'd3', hostname: 'PHONE', is_online: true, is_agentless: true },
        ],
      },
    });

    renderWithQueryClient(<TerminalPage />);

    expect(await screen.findByText('ONLINE-PC')).toBeInTheDocument();
    expect(screen.queryByText('OFFLINE-PC')).not.toBeInTheDocument();
    expect(screen.queryByText('PHONE')).not.toBeInTheDocument();
  });

  it('disables the Open Terminal button until a device is selected', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [] } });

    renderWithQueryClient(<TerminalPage />);

    expect(await screen.findByRole('button', { name: /open terminal/i })).toBeDisabled();
  });
});
