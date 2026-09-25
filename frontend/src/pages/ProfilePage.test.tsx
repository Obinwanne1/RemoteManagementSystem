import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi } from 'vitest';
import ProfilePage from './ProfilePage';

const mockUser = {
  id: 'u1', email: 'admin@test.local', full_name: 'Test Admin', role: 'admin', mfa_enabled: false,
};

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockUser, token: 'tok', login: vi.fn(), mfaLogin: vi.fn(), logout: vi.fn() }),
}));

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('ProfilePage', () => {
  it('renders the current user\'s name, email, and role on the profile tab', () => {
    renderWithQueryClient(<ProfilePage />);

    expect(screen.getByText('Test Admin')).toBeInTheDocument();
    expect(screen.getByText('admin@test.local')).toBeInTheDocument();
    expect(screen.getByText('ADMIN')).toBeInTheDocument();
  });

  it('shows MFA as disabled with a setup prompt when not enabled', () => {
    renderWithQueryClient(<ProfilePage />);

    fireEvent.click(screen.getByRole('button', { name: /two-factor auth/i }));

    expect(screen.getByRole('button', { name: /set up mfa/i })).toBeInTheDocument();
  });
});
