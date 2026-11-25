import React from "react";

export function VisuallyHidden({ children }: { children: React.ReactNode }) {
  return <div className="sr-only" aria-hidden="true">{children}</div>;
}
export default VisuallyHidden;
