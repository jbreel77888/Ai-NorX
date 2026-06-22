"use client";

import { ReactNode } from "react";

export function ChatLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">{children}</div>
  );
}
