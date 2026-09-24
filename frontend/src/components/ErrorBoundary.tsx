import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Without this, an uncaught render exception (e.g. .map() over undefined because
 * an API response shape changed) unmounts the entire component tree with no
 * user-visible message — just a blank page (React 16+ behavior). See
 * audits/error_handling_audit.md Finding A9.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // eslint-disable-next-line no-console
    console.error('Render error:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
          <h2 className="text-lg font-semibold text-gray-900">Something went wrong.</h2>
          <p className="max-w-md text-sm text-gray-500">
            {this.state.error.message || 'An unexpected error occurred while rendering this page.'}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
