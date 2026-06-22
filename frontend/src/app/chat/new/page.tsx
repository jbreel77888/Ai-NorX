"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Loader2 } from "lucide-react";
import { conversationsApi, agentsApi } from "@/lib/api";

export default function NewChatPage() {
  const router = useRouter();
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    if (!isLoaded || !isSignedIn) return;

    async function startChat() {
      try {
        const token = (await getToken()) || "";
        if (!token) return;

        // Get list of agents (default agent should be first)
        const agents = await agentsApi.list(token);
        if (!agents?.length) {
          setError("لا يوجد وكلاء متاحون. أنشئ وكيل أولاً.");
          return;
        }

        // Create new conversation with the first agent
        const conversation = await conversationsApi.create(
          { agent_id: agents[0].id, title: "محادثة جديدة" },
          token
        );

        if (!cancelled) {
          router.replace(`/chat/${conversation.id}`);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "حدث خطأ غير متوقع");
        }
      }
    }

    startChat();
    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn, getToken, router]);

  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-muted/30">
      <div className="text-center">
        {error ? (
          <>
            <p className="text-destructive mb-4">{error}</p>
            <button
              onClick={() => router.push("/agents")}
              className="text-primary underline"
            >
              إنشاء وكيل جديد
            </button>
          </>
        ) : (
          <>
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">جارٍ إنشاء محادثة جديدة...</p>
          </>
        )}
      </div>
    </div>
  );
}
