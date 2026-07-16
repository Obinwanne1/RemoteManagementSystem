import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Terminal, Send, X } from 'lucide-react';
import api from '../api/client';
import type { Device } from '../api/types';

interface TermOutput {
  output: string;
  is_complete: boolean;
}

interface SessionState {
  sessionId: string;
  deviceId: string;
  deviceName: string;
  history: Array<{ cmd: string; out: string }>;
}

export default function TerminalPage() {
  const [selectedDevice, setSelectedDevice] = useState('');
  const [session, setSession] = useState<SessionState | null>(null);
  const [cmd, setCmd] = useState('');
  const [historyIdx, setHistoryIdx] = useState(-1);
  const outputRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: devicesData } = useQuery<{ items: Device[] }>({
    queryKey: ['devices-online'],
    queryFn: () => api.get('/devices/', { params: { per_page: 100 } }).then((r) => r.data),
  });

  const onlineDevices = (devicesData?.items ?? []).filter((d) => d.is_online && !d.is_agentless);

  const openSession = useMutation({
    mutationFn: (device_id: string) =>
      api.post('/terminal/sessions', { device_id }).then((r) => r.data),
    onSuccess: (data, device_id) => {
      const dev = onlineDevices.find((d) => d.id === device_id);
      setSession({
        sessionId: data.session_id ?? data.id,
        deviceId: device_id,
        deviceName: dev?.display_name || dev?.hostname || device_id,
        history: [],
      });
      setTimeout(() => inputRef.current?.focus(), 100);
    },
  });

  const sendCmd = useMutation({
    mutationFn: ({ sessionId, command }: { sessionId: string; command: string }) =>
      api.post(`/terminal/sessions/${sessionId}/commands`, { command }).then((r) => r.data as TermOutput),
    onSuccess: (data, vars) => {
      setSession((prev) => prev ? {
        ...prev,
        history: [...prev.history, { cmd: vars.command, out: data.output ?? '' }],
      } : prev);
      setCmd('');
      setHistoryIdx(-1);
    },
  });

  const closeSession = useMutation({
    mutationFn: (sessionId: string) => api.delete(`/terminal/sessions/${sessionId}`),
    onSuccess: () => setSession(null),
  });

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [session?.history]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && cmd.trim() && session && !sendCmd.isPending) {
      sendCmd.mutate({ sessionId: session.sessionId, command: cmd.trim() });
    }
    if (e.key === 'ArrowUp' && session) {
      const newIdx = Math.min(historyIdx + 1, session.history.length - 1);
      setHistoryIdx(newIdx);
      setCmd(session.history[session.history.length - 1 - newIdx]?.cmd ?? '');
    }
    if (e.key === 'ArrowDown') {
      const newIdx = Math.max(historyIdx - 1, -1);
      setHistoryIdx(newIdx);
      setCmd(newIdx === -1 ? '' : (session?.history[session.history.length - 1 - newIdx]?.cmd ?? ''));
    }
  };

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Remote Terminal</h1>
        <p className="text-sm text-gray-500">Run commands on online managed devices</p>
      </div>

      {!session ? (
        <div className="max-w-sm space-y-3">
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">Target Device</label>
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-400 bg-white"
            >
              <option value="">Select online device…</option>
              {onlineDevices.map((d) => (
                <option key={d.id} value={d.id}>{d.display_name || d.hostname}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => openSession.mutate(selectedDevice)}
            disabled={!selectedDevice || openSession.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-brand-500 text-white text-sm font-semibold rounded-lg hover:bg-brand-600 disabled:opacity-50 transition"
          >
            <Terminal size={15} />
            {openSession.isPending ? 'Connecting…' : 'Open Terminal'}
          </button>
          {openSession.isError && (
            <p className="text-xs text-red-600">
              {(openSession.error as any)?.response?.data?.error ?? 'Failed to open session'}
            </p>
          )}
        </div>
      ) : (
        <div className="flex flex-col h-[calc(100vh-200px)] bg-gray-900 rounded-xl overflow-hidden border border-gray-700">
          {/* Terminal header */}
          <div className="flex items-center justify-between px-4 py-2.5 bg-gray-800 border-b border-gray-700">
            <div className="flex items-center gap-2">
              <Terminal size={14} className="text-green-400" />
              <span className="text-sm font-mono text-green-400">{session.deviceName}</span>
              <span className="text-xs text-gray-500 font-mono">· session active</span>
            </div>
            <button
              onClick={() => closeSession.mutate(session.sessionId)}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-red-400 transition"
            >
              <X size={13} />
              Close
            </button>
          </div>

          {/* Output area */}
          <div ref={outputRef} className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-sm">
            <p className="text-gray-500 text-xs">Connected to {session.deviceName}. Type commands below.</p>
            {session.history.map((h, i) => (
              <div key={i} className="space-y-1">
                <p className="text-green-400">
                  <span className="text-gray-500">$</span> {h.cmd}
                </p>
                {h.out && (
                  <pre className="text-gray-300 whitespace-pre-wrap text-xs leading-relaxed">{h.out}</pre>
                )}
              </div>
            ))}
            {sendCmd.isPending && (
              <p className="text-yellow-400 text-xs animate-pulse">Running…</p>
            )}
          </div>

          {/* Input */}
          <div className="flex items-center gap-2 px-4 py-3 bg-gray-800 border-t border-gray-700">
            <span className="text-green-400 font-mono text-sm shrink-0">$</span>
            <input
              ref={inputRef}
              type="text"
              value={cmd}
              onChange={(e) => setCmd(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sendCmd.isPending}
              placeholder="Enter command…"
              className="flex-1 bg-transparent text-gray-100 font-mono text-sm outline-none placeholder-gray-600 disabled:opacity-50"
              autoComplete="off"
              spellCheck={false}
            />
            <button
              onClick={() => cmd.trim() && sendCmd.mutate({ sessionId: session.sessionId, command: cmd.trim() })}
              disabled={!cmd.trim() || sendCmd.isPending}
              className="p-1.5 text-gray-400 hover:text-green-400 disabled:opacity-30 transition"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
