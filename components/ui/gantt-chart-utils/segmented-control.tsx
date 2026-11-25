import React from "react";

export function SegmentedControl({
  value,
  onValueChange,
  options,
  className,
}: {
  value: string;
  onValueChange: (val: any) => void;
  options: { value: string; label: string }[];
  className?: string;
  size?: string;
  label?: string;
}) {
  return (
    <div className={`inline-flex rounded-xl bg-white/5 p-1 border border-white/10 text-xs ${className || ""}`}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onValueChange(opt.value)}
          className={`px-3 py-1 rounded-lg font-semibold transition ${
            value === opt.value
              ? "bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-sm"
              : "text-gray-400 hover:text-white"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
export default SegmentedControl;
