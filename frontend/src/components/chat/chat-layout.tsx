"use client";

import { useState, ReactNode } from "react";
import { Menu } from "lucide-react";
import { Sidebar, MobileSidebar } from "./sidebar";

export function ChatLayout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background-strong">
      {/* Desktop Sidebar - Onyx style */}
      <aside className="w-64 shrink-0 hidden md:block">
        <Sidebar />
      </aside>

      {/* Mobile Sidebar */}
      <MobileSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main Content - Onyx style */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-background-strong">
        {/* Mobile Header with menu button */}
        <div className="md:hidden flex items-center p-2 border-b border-border-02 bg-background-strong">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-md hover:bg-background-weak"
          >
            <Menu className="w-4 h-4 text-text-05" />
          </button>
          <div className="flex items-center gap-1.5 mr-2">
            <div className="w-5 h-5 rounded bg-accent-strong flex items-center justify-center">
              <span className="text-white font-bold text-[10px]">N</span>
            </div>
            <span className="text-sm font-medium text-text-05">Ai NorX</span>
          </div>
        </div>

        {children}
      </main>
    </div>
  );
}
