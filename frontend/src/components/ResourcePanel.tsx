"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, ResourceResponse } from "@/lib/api";

interface ResourcePanelProps {
  refreshKey?: number;
}

export default function ResourcePanel({ refreshKey }: ResourcePanelProps) {
  const { token } = useAuth();
  const [resources, setResources] = useState<ResourceResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchResources = async () => {
    if (!token) return;
    try {
      const data = await api.getResources(token);
      setResources(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResources();
  }, [token, refreshKey]);

  const typeIcon = (type: string) => {
    if (type.includes("s3")) return "S3";
    if (type.includes("ec2")) return "EC2";
    return "?";
  };

  const typeBg = (type: string) => {
    if (type.includes("s3")) return "bg-orange-600";
    if (type.includes("ec2")) return "bg-green-600";
    return "bg-gray-600";
  };

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
        My Resources
      </h2>
      {loading ? (
        <div className="text-gray-500 text-sm">Loading...</div>
      ) : resources.length === 0 ? (
        <div className="text-gray-500 text-sm">No resources yet. Use the chat to create some.</div>
      ) : (
        <div className="space-y-2">
          {resources.map((r) => (
            <div
              key={r.id}
              className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm"
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`${typeBg(r.resource_type)} text-white text-xs px-2 py-0.5 rounded font-mono`}
                >
                  {typeIcon(r.resource_type)}
                </span>
                <span className="font-medium truncate">{r.name}</span>
              </div>
              <div className="text-xs text-gray-500 space-y-0.5">
                {r.region && <div>Region: {r.region}</div>}
                {r.cloud_identifier && (
                  <div className="truncate">ID: {r.cloud_identifier}</div>
                )}
                <div>Status: {r.status}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
