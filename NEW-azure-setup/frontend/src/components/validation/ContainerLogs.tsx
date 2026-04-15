import { useEffect, useRef } from "react";
import { Terminal } from "lucide-react";

interface ContainerLogsProps {
  logs: string;
  isLive: boolean;
}

export default function ContainerLogs({ logs, isLive }: ContainerLogsProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-gray-700 bg-gray-950">
      <div className="flex items-center justify-between border-b border-gray-700 bg-gray-900 px-4 py-2">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-green-400" />
          <span className="text-sm font-medium text-gray-300">
            Container Logs
          </span>
          {isLive && (
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 animate-pulse rounded-full bg-green-500" />
              <span className="text-xs text-green-400">Live</span>
            </span>
          )}
        </div>
      </div>

      <div
        ref={containerRef}
        className="h-[400px] overflow-y-auto bg-gray-950 p-4 font-mono text-sm"
      >
        {logs ? (
          <pre className="whitespace-pre-wrap break-all text-gray-300">
            {logs}
          </pre>
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-gray-600">
              {isLive ? "Waiting for logs..." : "No logs available."}
            </p>
          </div>
        )}

        {isLive && logs && (
          <span className="inline-block h-4 w-2 animate-pulse bg-green-400" />
        )}
      </div>
    </div>
  );
}
