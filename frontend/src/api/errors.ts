import { AxiosError } from 'axios';

/**
 * Extracts a human-readable message from a failed API call. The API's error
 * responses normally use {"error": "..."} (see api/app.py's centralized error
 * handlers); a small number of endpoints (JWT auth failures pre-audit-fix)
 * used {"msg": "..."} instead, so both are checked here as a defensive measure.
 * See audits/error_handling_audit.md Finding C4.
 */
export function apiErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data;
    if (data && typeof data === 'object') {
      if (typeof data.error === 'string') return data.error;
      if (typeof data.msg === 'string') return data.msg;
    }
    if (err.response?.statusText) return err.response.statusText;
    return err.message || fallback;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}
