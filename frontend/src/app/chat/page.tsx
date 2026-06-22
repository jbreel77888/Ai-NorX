"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, useUser } from "@clerk/nextjs";
import { ChatLayout } from "@/components/chat/chat-layout";
import { Sidebar } from "@/components/chat/sidebar";
import { Loader2, Plus, Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { conversationsApi, agentsApi, Conversation, Agent } from "@/lib/api";

export default function ChatPage() {
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { user } = useUser();
  const [token, setToken] = useState("");
  const [defaultAgent, setDefaultAgent] = useState<Agent | null>(null);

  // Get token once signed in
  useEffect(() => {
    if (!isSignedIn) return;
    let active = true;
    getToken().then((t) => {
      if (active && t) setToken(t);
    });
    return () => {
      active = false;
    };
  }, [isSignedIn, getToken]);

  // Fetch default agent once we have a token
  useEffect(() => {
    if (!token) return;
    let active = true;
    agentsApi
      .list(token)
      .then((agents) => {
        if (active && agents?.length) setDefaultAgent(agents[0]);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [token]);

  // Redirect to sign-in if not signed in (after Clerk loads)
  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push("/sign-in");
    }
  }, [isLoaded, isSignedIn, router]);

  // Show loading state while Clerk is loading
  if (!isLoaded) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isSignedIn) {
    return null; // Will redirect via useEffect
  }

  const startNewChat = async () => {
    if (!token || !defaultAgent) return;
    try {
      const conv = await conversationsApi.create(
        { agent_id: defaultAgent.id, title: "محادثة جديدة" },
        token
      );
      router.push(`/chat/${conv.id}`);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <ChatLayout>
      <Sidebar />
      <div className="flex-1 flex flex-col items-center justify-center bg-muted/30">
        <div className="text-center max-w-2xl mx-auto p-8">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center mx-auto mb-6 shadow-lg">
            <Bot className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold mb-3">
            مرحباً {user?.firstName || user?.username || "بك"} 👋
          </h1>
          <p className="text-muted-foreground text-lg mb-8">
            منصة الوكلاء الأذكياء العربية. اختر محادثة من القائمة أو ابدأ محادثة جديدة.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-xl mx-auto">
            <button
              onClick={startNewChat}
              disabled={!token || !defaultAgent}
              className="p-6 rounded-xl border bg-card hover:shadow-md hover:border-primary/50 transition-all cursor-pointer disabled:opacity-50"
            >
              <div className="text-3xl mb-3">💬</div>
              <h3 className="font-semibold mb-1">ابدأ محادثة جديدة</h3>
              <p className="text-sm text-muted-foreground">
                تحدث مع أحد الوكلاء الأذكياء
              </p>
            </button>
            <a
              href="/agents"
              className="p-6 rounded-xl border bg-card hover:shadow-md hover:border-primary/50 transition-all cursor-pointer block"
            >
              <div className="text-3xl mb-3">🤖</div>
              <h3 className="font-semibold mb-1">أنشئ وكيل جديد</h3>
              <p className="text-sm text-muted-foreground">
                خصص وكيلك الذكي الخاص
              </p>
            </a>
          </div>

          <div className="mt-8 text-xs text-muted-foreground">
            <p>
              المتصل بـ:{" "}
              <span className="font-mono">
                {process.env.NEXT_PUBLIC_API_URL}
              </span>
            </p>
          </div>
        </div>
      </div>
    </ChatLayout>
  );
}
