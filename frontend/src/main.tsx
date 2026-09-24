import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query';
import './index.css';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ToastProvider, notifyError } from './components/Toast';
import { apiErrorMessage } from './api/errors';

const queryClient = new QueryClient({
  // Without these, a page whose component doesn't check `isError` itself (most
  // of them — see audits/error_handling_audit.md Finding A10) renders a failed
  // fetch as silently-empty data with zero indication anything went wrong.
  queryCache: new QueryCache({
    onError: (err, query) => {
      // Don't toast a background refetch of data that's already showing —
      // only surface it when there's nothing on screen yet.
      if (query.state.data !== undefined) return;
      notifyError(apiErrorMessage(err, 'Failed to load data'));
    },
  }),
  mutationCache: new MutationCache({
    onError: (err) => {
      notifyError(apiErrorMessage(err, 'Action failed'));
    },
  }),
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
);
