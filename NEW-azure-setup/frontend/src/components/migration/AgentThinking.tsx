import { useEffect, useState } from "react";

interface AgentThinkingProps {
  message?: string;
  agentName?: string;
}

export default function AgentThinking({
  message = "Processing",
  agentName,
}: AgentThinkingProps) {
  const [dots, setDots] = useState("");

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 400);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-3 py-2">
      {/* Pulsing brain icon */}
      <div className="relative flex h-8 w-8 items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-[#0070AD]/20 animate-ping" />
        <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-[#0070AD]/10">
          <svg
            className="h-4 w-4 text-[#0070AD]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2a8 8 0 0 0-8 8c0 3.4 2.1 6.3 5 7.5V20a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-2.5c2.9-1.2 5-4.1 5-7.5a8 8 0 0 0-8-8z" />
            <path d="M9.5 22h5" />
            <path d="M8 14.5a4 4 0 0 1 0-5" />
            <path d="M16 14.5a4 4 0 0 0 0-5" />
          </svg>
        </div>
      </div>

      <div className="flex flex-col">
        {agentName && (
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[#0070AD]/60">
            {agentName}
          </span>
        )}
        <span className="text-sm text-[#1B365D] dark:text-gray-300 font-medium">
          {message}
          <span className="inline-block w-5 text-left text-[#0070AD]">{dots}</span>
        </span>
      </div>

      {/* Animated bar */}
      <div className="ml-auto flex items-center gap-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-3 w-1 rounded-full bg-[#0070AD]/40"
            style={{
              animation: `agentThinkingPulse 1.2s ease-in-out ${i * 0.15}s infinite`,
            }}
          />
        ))}
      </div>

      <style>{`
        @keyframes agentThinkingPulse {
          0%, 100% { transform: scaleY(0.4); opacity: 0.4; }
          50% { transform: scaleY(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
