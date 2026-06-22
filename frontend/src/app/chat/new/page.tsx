"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Loader2, Bot } from "lucide-react";

export default function NewChatPage() {
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    let active = true;

    (async () => {
      try {
        const token = (await getToken()) || "";
        if (!token || !active) return;

        // Import API client
        const { conversationsApi, agentsApi } = await import("@/lib/api");

        // Get the universal NorX agent (first one)
        const agents = await agentsApi.list(token);
        if (!agents?.length) {
          if (active) setError("لا يوجد وكلاء متاحون");
          return;
        }

        // Create new conversation with the universal agent
        const conversation = await conversationsApi.create(
          { agent_id: agents[0].id, title: "محادثة جديدة" },
          token
        );

        if (active) router.replace(`/chat/${conversation.id}`);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "حدث خطأ");
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [isLoaded, isSignedIn, getToken, router]);

  if (!isLoaded) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center">
        {error ? (
          <p className="text-destructive">{error}</p>
        ) : (
          <>
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center mx-auto mb-4">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <Loader2 className="w-5 h-5 animate-spin mx-auto mb-3 text-primary" />
            <p className="text-muted-foreground text-sm">جارٍ إنشاء محادثة جديدة...</p>
          </>
        )}
      </div>
    </div>
  );
}
