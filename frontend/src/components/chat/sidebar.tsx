"use client";

import { UserButton } from "@clerk/nextjs";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Plus, MessageSquare, Settings, Bot, Menu, X } from "lucide-react";
import { conversationsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function Sidebar() {
  const router = useRouter();
  const { getToken, isSignedIn } = useAuth();
  const [token, setToken] = useState<string>("");
  const [isOpen, setIsOpen] = useState(false);

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
    staleTime: 30000,
  });

  const newConversationMutation = useMutation({
    mutationFn: () => conversationsApi.create({ title: "محادثة جديدة" }, token),
    onSuccess: (conv) => router.push(`/chat/${conv.id}`),
  });

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="md:hidden fixed top-4 right-4 z-50 p-2 rounded-lg bg-background border shadow-md"
      >
        {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {isOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside
        className={cn(
          "w-72 bg-card border-l flex flex-col h-full shrink-0",
        )}
      >
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Ai NorX
            </h1>
            <UserButton
              appearance={{
                elements: { avatarBox: "w-8 h-8" },
              }}
            />
          </div>

          <Button
            onClick={() => newConversationMutation.mutate()}
            disabled={newConversationMutation.isPending || !token}
            className="w-full"
          >
            <Plus className="w-4 h-4 ml-2" />
            محادثة جديدة
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          <div className="text-xs font-medium text-muted-foreground px-2 py-2">
            المحادثات
          </div>
          {conversations?.map((conv) => (
            <button
              key={conv.id}
              onClick={() => router.push(`/chat/${conv.id}`)}
              className="w-full flex items-start gap-2 p-2 rounded-lg hover:bg-accent text-right"
            >
              <MessageSquare className="w-4 h-4 mt-0.5 text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                  {conv.title || "محادثة"}
                </div>
                <div className="text-xs text-muted-foreground">
                  {conv.message_count} رسالة
                </div>
              </div>
            </button>
          ))}
          {!conversations?.length && token && (
            <div className="text-center text-muted-foreground text-sm p-4">
              لا توجد محادثات بعد
            </div>
          )}
        </div>

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
