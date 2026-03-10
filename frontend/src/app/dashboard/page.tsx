"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import ChatInterface from "@/components/ChatInterface";
import ResourcePanel from "@/components/ResourcePanel";
import ExecutionLog from "@/components/ExecutionLog";

export default function DashboardPage() {
  const { token, loading } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"resources" | "logs">("resources");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!loading && !token) {
      router.replace("/login");
    }
  }, [token, loading, router]);

  if (loading || !token) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    );
  }

  const handleAction = () => setRefreshKey((k) => k + 1);

  return (
    <div className="flex flex-col h-screen">
      <Navbar />
      <div className="flex-1 flex overflow-hidden">
        {/* Main chat area */}
        <div className="flex-1 flex flex-col border-r border-gray-800">
          <ChatInterface onAction={handleAction} />
        </div>

        {/* Right sidebar */}
        <div className="w-80 flex flex-col bg-gray-900/50 overflow-hidden">
          <div className="flex border-b border-gray-800">
            <button
              onClick={() => setActiveTab("resources")}
              className={`flex-1 py-3 text-xs font-medium uppercase tracking-wider transition-colors ${
                activeTab === "resources"
                  ? "text-primary-400 border-b-2 border-primary-400"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Resources
            </button>
            <button
              onClick={() => setActiveTab("logs")}
              className={`flex-1 py-3 text-xs font-medium uppercase tracking-wider transition-colors ${
                activeTab === "logs"
                  ? "text-primary-400 border-b-2 border-primary-400"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              History
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {activeTab === "resources" ? (
              <ResourcePanel refreshKey={refreshKey} />
            ) : (
              <ExecutionLog refreshKey={refreshKey} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
