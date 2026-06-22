"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Loader2 } from "lucide-react";
import { conversationsApi, agentsApi } from "@/lib/api";

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

        const agents = await agentsApi.list(token);
        if (!agents?.length) {
          if (active) setError("لا يوجد وكلاء متاحون");
          return;
        }

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
    <div className="flex-1 flex items-center justify-center bg-muted/30">
      <div className="text-center">
        {error ? (
          <p className="text-destructive">{error}</p>
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
