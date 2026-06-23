"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth, useUser, UserButton } from "@clerk/nextjs";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  MessageSquare,
  Settings,
  Search,
  X,
  FolderOpen,
  MoreHorizontal,
} from "lucide-react";
import { conversationsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const router = useRouter();
  const pathname = usePathname();
  const { getToken, isSignedIn } = useAuth();
  const { user } = useUser();
  const [token, setToken] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!isSignedIn) return;
    let active = true;
    getToken().then((t) => {
      if (active && t) setToken(t);
    });
    return () => {
      active = false;
    };
  }, [getToken, isSignedIn]);

  const { data: conversations } = useQuery({
    queryKey: ["conversations", token],
    queryFn: () => conversationsApi.list(token),
    enabled: !!token,
    retry: false,
    staleTime: 10000,
  });

  const newConversationMutation = useMutation({
    mutationFn: () => conversationsApi.create({ title: "محادثة جديدة" }, token),
    onSuccess: (conv) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      router.push(`/chat/${conv.id}`);
      onNavigate?.();
    },
  });

  const filteredConversations = conversations?.filter((c) =>
    c.title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-full flex-col bg-background-weak border-l border-border-02">
      {/* Header - Onyx style */}
      <div className="flex items-center justify-between px-3 h-12 border-b border-border-02 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-accent-strong flex items-center justify-center">
            <span className="text-white font-bold text-xs">N</span>
          </div>
          <span className="font-semibold text-sm text-text-05">Ai NorX</span>
        </div>
        <UserButton
          appearance={{
            elements: { avatarBox: "w-6 h-6" },
          }}
        />
      </div>

      {/* New Chat Button - Onyx style */}
      <div className="p-2 shrink-0">
        <Button
          onClick={() => newConversationMutation.mutate()}
          disabled={newConversationMutation.isPending || !token}
          className="w-full justify-start gap-2 bg-background-strong border border-border-01 hover:bg-background-weaker text-text-05"
          variant="outline"
        >
          <Plus className="w-4 h-4" />
          محادثة جديدة
        </Button>
      </div>

      {/* Search - Onyx style */}
      <div className="px-2 pb-2 shrink-0">
        <div className="relative">
          <Search className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-02" />
          <Input
            placeholder="بحث في المحادثات..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-8 pr-8 text-sm bg-background-strong border-border-02 focus-visible:ring-1 focus-visible:ring-accent-weak"
          />
        </div>
      </div>

      {/* Conversations List - Onyx style */}
      <div className="flex-1 overflow-y-auto px-1.5 pb-2 no-scrollbar">
        {filteredConversations?.map((conv) => {
          const isActive = pathname === `/chat/${conv.id}`;
          return (
            <button
              key={conv.id}
              onClick={() => {
                router.push(`/chat/${conv.id}`);
                onNavigate?.();
              }}
              className={cn(
                "w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-sm transition-colors text-right group mb-0.5",
                isActive
                  ? "bg-background-strong text-text-05"
                  : "hover:bg-background-weaker text-text-03 hover:text-text-05"
              )}
            >
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              <span className="flex-1 truncate text-left">
                {conv.title || "محادثة جديدة"}
              </span>
              {conv.message_count > 0 && (
                <span className="text-[10px] text-text-02 shrink-0">
                  {conv.message_count}
                </span>
              )}
            </button>
          );
        })}
        {!filteredConversations?.length && token && (
          <div className="text-center text-text-02 text-xs py-8">
            لا توجد محادثات
          </div>
        )}
      </div>

      {/* Footer - Onyx style */}
      <div className="p-1.5 border-t border-border-02 shrink-0">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 text-text-03 hover:text-text-05 hover:bg-background-weaker"
          onClick={() => {
            router.push("/files");
            onNavigate?.();
          }}
        >
          <FolderOpen className="w-4 h-4" />
          ملفاتي
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 text-text-03 hover:text-text-05 hover:bg-background-weaker"
          onClick={() => {
            router.push("/settings");
            onNavigate?.();
          }}
        >
          <Settings className="w-4 h-4" />
          الإعدادات
        </Button>
      </div>
    </div>
  );
}

export function MobileSidebar({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  if (!isOpen) return null;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 z-40 md:hidden"
        onClick={onClose}
      />
      <div className="fixed inset-y-0 right-0 w-64 z-50 md:hidden">
        <div className="relative h-full">
          <button
            onClick={onClose}
            className="absolute left-2 top-2 z-10 p-1 rounded-md hover:bg-background-weaker"
          >
            <X className="w-4 h-4" />
          </button>
          <Sidebar onNavigate={onClose} />
        </div>
      </div>
    </>
  );
}
