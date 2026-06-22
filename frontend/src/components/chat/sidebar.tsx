"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth, useUser, UserButton } from "@clerk/nextjs";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, MessageSquare, Settings, Search, X } from "lucide-react";
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
    <div className="flex h-full flex-col bg-secondary/40">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">N</span>
          </div>
          <span className="font-semibold">Ai NorX</span>
        </div>
        <UserButton
          appearance={{
            elements: { avatarBox: "w-7 h-7" },
          }}
        />
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <Button
          onClick={() => newConversationMutation.mutate()}
          disabled={newConversationMutation.isPending || !token}
          className="w-full justify-start gap-2 bg-primary hover:bg-primary/90"
        >
          <Plus className="w-4 h-4" />
          محادثة جديدة
        </Button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <Input
            placeholder="بحث في المحادثات..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 pr-8 text-sm bg-background/50 border-0 focus-visible:ring-1"
          />
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
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
                "w-full flex items-center gap-2 p-2.5 rounded-lg text-sm transition-colors text-right group mb-0.5",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "hover:bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              <span className="flex-1 truncate">
                {conv.title || "محادثة جديدة"}
              </span>
              {conv.message_count > 0 && (
                <span className="text-[10px] text-muted-foreground/70 shrink-0">
                  {conv.message_count}
                </span>
              )}
            </button>
          );
        })}
        {!filteredConversations?.length && token && (
          <div className="text-center text-muted-foreground text-xs py-8">
            لا توجد محادثات
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-2 border-t border-border">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2 text-muted-foreground hover:text-foreground"
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
      <div className="fixed inset-y-0 right-0 w-72 z-50 md:hidden">
        <div className="relative h-full">
          <button
            onClick={onClose}
            className="absolute left-2 top-2 z-10 p-1 rounded-md hover:bg-secondary"
          >
            <X className="w-4 h-4" />
          </button>
          <Sidebar onNavigate={onClose} />
        </div>
      </div>
    </>
  );
}
