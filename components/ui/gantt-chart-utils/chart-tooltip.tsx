import React from "react";

export function ChartTooltip({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; value: string; color?: string }[];
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#121217] p-2.5 text-xs text-white shadow-xl min-w-[150px]">
      <div className="font-bold text-slate-200 mb-1">{title}</div>
      <div className="space-y-0.5">
        {rows.map((r, i) => (
          <div key={i} className="flex justify-between gap-3 text-[11px] text-gray-400">
            <span>{r.label}:</span>
            <span className="font-semibold text-white" style={r.color ? { color: r.color } : {}}>
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
export default ChartTooltip;
