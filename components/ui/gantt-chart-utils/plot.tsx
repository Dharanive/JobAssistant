import { useState } from "react";

export const TICK_CLASS = "text-[10px] font-mono fill-gray-400";
export const DRAW_IN_CLASS = "transition-all duration-300";

export const svgId = (id: string) => id.replace(/[^a-zA-Z0-9-_]/g, "_");

export function useDrawIn() {
  return true;
}

export function useChartCursor(length: number) {
  const [active, setActive] = useState<number | null>(null);
  const keyProps = {
    tabIndex: 0,
    onKeyDown: (e: any) => {
      if (e.key === "ArrowDown" || e.key === "ArrowRight") {
        setActive((prev) => (prev === null ? 0 : Math.min(length - 1, prev + 1)));
      } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
        setActive((prev) => (prev === null ? 0 : Math.max(0, prev - 1)));
      }
    },
  };
  return { active, setActive, keyProps };
}

export function PlotAnnouncer({ message }: { message: string }) {
  return <div className="sr-only" aria-live="polite">{message}</div>;
}

export function PlotTip({ x, y, children }: any) {
  return (
    <div
      style={{ left: x, top: y }}
      className="pointer-events-none absolute -translate-x-1/2 -translate-y-full pb-2 z-30"
    >
      {children}
    </div>
  );
}
