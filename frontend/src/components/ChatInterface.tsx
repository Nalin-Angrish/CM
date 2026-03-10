"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { api, PromptResponse, ConversationMessage } from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "system";
  content: string;
  data?: PromptResponse;
  options?: string[];
  timestamp: Date;
}

interface ChatInterfaceProps {
  onAction?: () => void;
}

export default function ChatInterface({ onAction }: ChatInterfaceProps) {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "system",
      content:
        'Welcome to Cloud Manager. Describe what cloud resources you need and I\'ll handle the rest.\n\nExamples:\n- "Create a private S3 bucket called my-logs in us-east-1"\n- "Launch a t2.micro EC2 instance named web-server"\n- "Delete the S3 bucket called old-data"\n- "How many EC2 instances do I have?"',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const buildHistory = (): ConversationMessage[] => {
    // Build conversation context from all previous messages (excluding welcome).
    // Note: the current user message is sent separately as `prompt` and must
    // NOT be included here to avoid duplication in the LLM prompt.
    return messages
      .filter((m) => m.id !== "welcome")
      .slice(-10)
      .map((m) => ({
        role: m.role === "user" ? ("user" as const) : ("assistant" as const),
        content: m.content,
      }));
  };

  const handleOptionClick = (option: string) => {
    setInput(option);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !token || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history = buildHistory();
      const result = await api.submitPrompt(token, userMsg.content, history);
      let content: string;
      let options: string[] = [];

      if (result.status === "clarification") {
        content = result.message || "Could you provide more details?";
        options = result.options || [];
      } else if (result.status === "conversation") {
        content = result.message || "Here's what I found.";
      } else if (result.status === "completed") {
        // Prefer the LLM-interpreted message, fall back to raw result
        if (result.message) {
          content = result.message;
        } else if (result.result) {
          const r = result.result as Record<string, unknown>;
          content = (r.message as string) || "Action completed successfully.";
        } else {
          content = "Action completed successfully.";
        }
      } else if (result.status === "denied") {
        content = `Access denied: ${result.error}`;
      } else if (result.status === "failed") {
        content = `Error: ${result.error || "Request failed"}`;
      } else {
        content = result.message || `Error: ${result.error || "Unknown error occurred"}`;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: result.prompt_id,
          role: "system",
          content,
          data: result,
          options,
          timestamp: new Date(),
        },
      ]);
      onAction?.();
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "system",
          content: `Error: ${err instanceof Error ? err.message : "Request failed"}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-primary-600 text-white"
                  : "bg-gray-800 text-gray-200 border border-gray-700"
              }`}
            >
              {msg.content}
              {msg.options && msg.options.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {msg.options.map((opt) => (
                    <button
                      key={opt}
                      onClick={() => handleOptionClick(opt)}
                      className="px-3 py-1 text-xs bg-gray-700 hover:bg-primary-600 rounded-lg border border-gray-600 transition-colors"
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
              {msg.data?.parsed_action && msg.data.status === "completed" && (
                <details className="mt-2 pt-2 border-t border-gray-600">
                  <summary className="text-xs text-gray-400 cursor-pointer">
                    Execution details
                  </summary>
                  <pre className="text-xs mt-1 text-gray-400 overflow-x-auto">
                    {JSON.stringify(msg.data.parsed_action, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 border border-gray-700 rounded-2xl px-4 py-3 text-sm text-gray-400">
              <span className="inline-flex gap-1">
                <span className="animate-bounce">.</span>
                <span className="animate-bounce" style={{ animationDelay: "0.1s" }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: "0.2s" }}>.</span>
              </span>{" "}
              Processing your request
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe what you need (e.g., Create an S3 bucket called my-logs)"
            className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl focus:outline-none focus:border-primary-500 text-gray-100 text-sm placeholder-gray-500"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-6 py-3 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-xl font-medium text-sm transition-colors"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
