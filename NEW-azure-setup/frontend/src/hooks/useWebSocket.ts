import { useEffect, useRef, useCallback } from "react";
import { WebSocketManager } from "@/api/websocket";

interface UseWebSocketOptions {
  path?: string;
  autoConnect?: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { path = "/ws/events", autoConnect = true } = options;
  const managerRef = useRef<WebSocketManager | null>(null);
  const cleanupFns = useRef<Array<() => void>>([]);

  useEffect(() => {
    const manager = new WebSocketManager(path);
    managerRef.current = manager;

    if (autoConnect) {
      manager.connect();
    }

    return () => {
      cleanupFns.current.forEach((fn) => fn());
      cleanupFns.current = [];
      manager.disconnect();
      managerRef.current = null;
    };
  }, [path, autoConnect]);

  const on = useCallback(
    (type: string, handler: (data: unknown) => void) => {
      if (!managerRef.current) return () => {};
      const unsubscribe = managerRef.current.on(type, handler);
      cleanupFns.current.push(unsubscribe);
      return unsubscribe;
    },
    []
  );

  const send = useCallback((type: string, payload: unknown) => {
    managerRef.current?.send(type, payload);
  }, []);

  const connect = useCallback(() => {
    managerRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    managerRef.current?.disconnect();
  }, []);

  return { on, send, connect, disconnect, manager: managerRef };
}
