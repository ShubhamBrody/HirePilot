"use client";

import { useState, useRef, useEffect } from "react";
import { FiSend, FiDollarSign, FiLoader, FiTrash2 } from "react-icons/fi";
import { agentsApi } from "@/lib/api";
import toast from "react-hot-toast";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function SalaryNegotiatorPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm your AI salary negotiation advisor. Share details about the offer you've received " +
        "(role, company, base salary, stocks, bonus, location) and I'll help you evaluate it and prepare " +
        "a negotiation strategy. You can also ask me general questions about compensation benchmarks.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg: ChatMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history = messages
        .map((m) => ({ role: m.role, content: m.content }));

      const { data } = await agentsApi.run("salary_negotiator", {
        message: input,
        context: {},
        history,
      });

      const reply =
        data?.result?.data?.reply ||
        data?.result?.data?.response ||
        data?.data?.reply ||
        "I couldn't generate a response. Please try again.";

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply },
      ]);
    } catch {
      toast.error("Failed to get response");
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([
      {
        role: "assistant",
        content:
          "Chat cleared. Share a new offer or question and I'll help you negotiate!",
      },
    ]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <FiDollarSign className="h-6 w-6 text-green-500" /> Salary Negotiator
          </h1>
          <p className="text-sm text-[var(--muted-foreground)]">
            AI-powered salary negotiation advisor
          </p>
        </div>
        <button onClick={handleClear} className="btn-secondary flex items-center gap-1 text-sm">
          <FiTrash2 className="h-4 w-4" /> Clear Chat
        </button>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-1">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-brand-600 text-white"
                  : "bg-[var(--muted)] text-[var(--foreground)]"
              }`}
            >
              {msg.content.split("\n").map((line, j) => (
                <p key={j} className={j > 0 ? "mt-2" : ""}>
                  {line}
                </p>
              ))}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-[var(--muted)] rounded-xl px-4 py-3 text-sm flex items-center gap-2">
              <FiLoader className="h-4 w-4 animate-spin" /> Analyzing...
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2 border-t border-[var(--border)] pt-4">
        <input
          type="text"
          placeholder="Describe your offer, ask about benchmarks, or request counter-offer scripts..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          className="input flex-1"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="btn-primary flex items-center gap-1"
        >
          <FiSend className="h-4 w-4" /> Send
        </button>
      </div>
    </div>
  );
}
