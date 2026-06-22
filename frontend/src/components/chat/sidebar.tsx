"use client";

import { SignedIn, SignedOut, UserButton } from "@clerk/nextjs";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Plus, MessageSquare, Settings, Bot, Menu, X } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { conversationsApi, Conversation } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function Sidebar() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [token, setToken] = useState<string>("");
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    getToken().then(setToken);
  }, [getToken]);

  const { data: conversations } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => conversationsApi.list(token),
    enabled: !!token,
  });

  const newConversationMutation = useMutation({
    mutationFn: async () => {
      return conversationsApi.create({ title: "محادثة جديدة" }, token);
    },
    onSuccess: (conv) => {
      router.push(`/chat/${conv.id}`);
    },
  });

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="md:hidden fixed top-4 right-4 z-50 p-2 rounded-lg bg-background border shadow-md"
      >
        {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {/* Backdrop */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside
        className={cn(
          "w-72 bg-card border-l flex flex-col h-full transition-transform",
          "fixed md:relative z-40 inset-y-0 right-0",
          isOpen ? "translate-x-0" : "translate-x-full md:translate-x-0"
        )}
      >
        {/* Header */}
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Ai NorX
            </h1>
            <SignedIn>
              <UserButton
                appearance={{
                  elements: {
                    avatarBox: "w-8 h-8",
                  },
                }}
              />
            </SignedIn>
          </div>

          <Button
            onClick={() => newConversationMutation.mutate()}
            disabled={newConversationMutation.isPending}
            className="w-full"
          >
            <Plus className="w-4 h-4 ml-2" />
            محادثة جديدة
          </Button>
        </div>

        {/* Conversations list */}
        <div className="flex-1 overflow-y-auto p-2">
          <div className="text-xs font-medium text-muted-foreground px-2 py-2">
            المحادثات
          </div>
          {conversations?.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              onClick={() => {
                router.push(`/chat/${conv.id}`);
                setIsOpen(false);
              }}
            />
          ))}
          {!conversations?.length && (
            <div className="text-center text-muted-foreground text-sm p-4">
              لا توجد محادثات بعد
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-2 border-t">
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={() => router.push("/agents")}
          >
            <Bot className="w-4 h-4 ml-2" />
            الوكلاء
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={() => router.push("/settings")}
          >
            <Settings className="w-4 h-4 ml-2" />
            الإعدادات
          </Button>
        </div>
      </aside>
    </>
  );
}

function ConversationItem({
  conversation,
  onClick,
}: {
  conversation: Conversation;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-start gap-2 p-2 rounded-lg hover:bg-accent text-right group"
    >
      <MessageSquare className="w-4 h-4 mt-0.5 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">
          {conversation.title || "محادثة"}
        </div>
        <div className="text-xs text-muted-foreground">
          {conversation.message_count} رسالة
        </div>
      </div>
    </button>
  );
}
