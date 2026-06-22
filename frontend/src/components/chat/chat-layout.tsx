"use client";

import { useState, ReactNode } from "react";
import { Menu } from "lucide-react";
import { Sidebar, MobileSidebar } from "./sidebar";

export function ChatLayout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop Sidebar */}
      <aside className="w-72 shrink-0 hidden md:block">
        <Sidebar />
      </aside>

      {/* Mobile Sidebar */}
      <MobileSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 relative">
        {/* Mobile Header with menu button */}
        <div className="md:hidden flex items-center p-2 border-b border-border bg-background">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-md hover:bg-secondary"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="mr-2 font-semibold">Ai NorX</span>
        </div>

        {children}
      </main>
    </div>
  );
}
