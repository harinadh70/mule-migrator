import { useEffect, useState, useRef } from "react";

interface AnimatedCounterProps {
  value: number;
  duration?: number;
  format?: "number" | "percentage" | "duration" | "compact";
  className?: string;
}

function formatValue(val: number, format: string): string {
  switch (format) {
    case "percentage":
      return `${val.toFixed(1)}%`;
    case "duration":
      if (val >= 60000) return `${(val / 60000).toFixed(1)}m`;
      return `${(val / 1000).toFixed(1)}s`;
    case "compact":
      if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
      if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
      return val.toLocaleString();
    default:
      return val.toLocaleString();
  }
}

export default function AnimatedCounter({
  value,
  duration = 1200,
  format = "number",
  className = "",
}: AnimatedCounterProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const animRef = useRef<number>(0);
  const startTimeRef = useRef<number>(0);
  const startValueRef = useRef<number>(0);

  useEffect(() => {
    if (value === 0) {
      setDisplayValue(0);
      return;
    }

    startValueRef.current = displayValue;
    startTimeRef.current = performance.now();

    function animate(now: number) {
      const elapsed = now - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // Ease-out cubic for smooth deceleration
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startValueRef.current + (value - startValueRef.current) * eased;

      setDisplayValue(current);

      if (progress < 1) {
        animRef.current = requestAnimationFrame(animate);
      } else {
        setDisplayValue(value);
      }
    }

    animRef.current = requestAnimationFrame(animate);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [value, duration]);

  return (
    <span className={`tabular-nums ${className}`}>
      {formatValue(
        format === "percentage" || format === "duration" ? displayValue : Math.floor(displayValue),
        format
      )}
    </span>
  );
}
