import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import SoftwarePatchesPage from './SoftwarePatchesPage';
import api from '../api/client';

vi.mock('../api/client', () => ({
  default: { get: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('SoftwarePatchesPage', () => {
  it('shows a prompt to select a device when none is selected', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [] } });

    renderWithQueryClient(<SoftwarePatchesPage />);

    expect(await screen.findByText(/select a device to view installed software/i)).toBeInTheDocument();
  });

  it('renders software rows for the selected device', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/devices/') {
        return Promise.resolve({
          data: { items: [{ id: 'd1', hostname: 'DESKTOP-1', is_online: true, is_agentless: false }] },
        });
      }
      return Promise.resolve({
        data: { software: [{ name: '7-Zip', version: '23.01', publisher: 'Igor Pavlov' }] },
      });
    });

    const user = userEvent.setup();
    renderWithQueryClient(<SoftwarePatchesPage />);

    // Wait for the devices query to resolve and populate the <option>
    // before selecting it — the combobox exists immediately, but with only
    // the placeholder option until then.
    await screen.findByText('DESKTOP-1', { exact: false });
    const select = screen.getByRole('combobox');
    await user.selectOptions(select, 'd1');

    expect(await screen.findByText('7-Zip')).toBeInTheDocument();
  });
});
