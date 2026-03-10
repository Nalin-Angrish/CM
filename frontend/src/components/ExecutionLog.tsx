"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, ExecutionLogResponse } from "@/lib/api";

interface ExecutionLogProps {
  refreshKey?: number;
}

export default function ExecutionLog({ refreshKey }: ExecutionLogProps) {
  const { token } = useAuth();
  const [logs, setLogs] = useState<ExecutionLogResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    api
      .getExecutionLogs(token)
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, refreshKey]);

  const statusColor = (status: string) => {
    if (status === "success") return "text-green-400";
    if (status === "failed") return "text-red-400";
    if (status === "denied") return "text-yellow-400";
    return "text-gray-400";
  };

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
        Execution History
      </h2>
      {loading ? (
        <div className="text-gray-500 text-sm">Loading...</div>
      ) : logs.length === 0 ? (
        <div className="text-gray-500 text-sm">No execution history yet.</div>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <div
              key={log.id}
              className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs text-gray-300">
                  {log.tool_name || log.action}
                </span>
                <span className={`text-xs font-medium ${statusColor(log.status)}`}>
                  {log.status}
                </span>
              </div>
              {log.duration_ms != null && (
                <div className="text-xs text-gray-500">{log.duration_ms}ms</div>
              )}
              {log.error_message && (
                <div className="text-xs text-red-400 mt-1">{log.error_message}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
