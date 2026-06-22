"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Plus, Bot, MessageSquare, Loader2 } from "lucide-react";
import { agentsApi, conversationsApi, Agent } from "@/lib/api";
import { Sidebar } from "@/components/chat/sidebar";
import { ChatLayout } from "@/components/chat/chat-layout";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function AgentsPage() {
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [token, setToken] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);

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

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push("/sign-in");
    }
  }, [isLoaded, isSignedIn, router]);

  const { data: agents } = useQuery({
    queryKey: ["agents", token],
    queryFn: () => agentsApi.list(token),
    enabled: !!token,
    retry: false,
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<Agent>) => agentsApi.create(data, token),
    onSuccess: () => {
      toast.success("تم إنشاء الوكيل بنجاح");
      setIsCreateOpen(false);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (!isLoaded) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isSignedIn) return null;

  return (
    <ChatLayout>
      <Sidebar />
      <div className="flex-1 overflow-y-auto">
        <header className="border-b p-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold">الوكلاء</h1>
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="w-4 h-4 ml-2" />
                وكيل جديد
              </Button>
            </DialogTrigger>
            <CreateAgentDialog
              onSubmit={(data) => createMutation.mutate(data)}
              isPending={createMutation.isPending}
            />
          </Dialog>
        </header>

        <div className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents?.map((agent) => (
              <AgentCard key={agent.id} agent={agent} token={token} />
            ))}
            {!agents?.length && (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <Bot className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>لا يوجد وكلاء بعد. أنشئ أول وكيل لك!</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </ChatLayout>
  );
}

function AgentCard({ agent, token }: { agent: Agent; token: string }) {
  const router = useRouter();

  const startChat = async () => {
    try {
      const conv = await conversationsApi.create({ agent_id: agent.id }, token);
      router.push(`/chat/${conv.id}`);
    } catch (err) {
      toast.error("فشل إنشاء المحادثة");
    }
  };

  return (
    <div className="border rounded-xl p-4 hover:shadow-md transition-shadow bg-card">
      <div className="flex items-start gap-3 mb-3">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <Bot className="w-5 h-5 text-white" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold">{agent.name}</h3>
          <p className="text-xs text-muted-foreground">{agent.llm_model}</p>
        </div>
      </div>
      <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
        {agent.description || "لا يوجد وصف"}
      </p>
      <Button size="sm" className="w-full" onClick={startChat}>
        <MessageSquare className="w-4 h-4 ml-1" />
        محادثة
      </Button>
    </div>
  );
}

function CreateAgentDialog({
  onSubmit,
  isPending,
}: {
  onSubmit: (data: Partial<Agent>) => void;
  isPending: boolean;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState(
    "أنت مساعد ذكي تساعد المستخدمين في مهامهم المختلفة. تحدث العربية بطلاقة."
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ name, description, system_prompt: systemPrompt });
  };

  return (
    <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>إنشاء وكيل جديد</DialogTitle>
      </DialogHeader>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <Label htmlFor="name">اسم الوكيل</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="مساعد التسويق"
            required
          />
        </div>
        <div>
          <Label htmlFor="description">الوصف (اختياري)</Label>
          <Input
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="وصف مختصر للوكيل"
          />
        </div>
        <div>
          <Label htmlFor="system-prompt">تعليمات النظام</Label>
          <Textarea
            id="system-prompt"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="min-h-[120px]"
            required
          />
        </div>
        <Button type="submit" disabled={isPending} className="w-full">
          {isPending ? "جارٍ الإنشاء..." : "إنشاء الوكيل"}
        </Button>
      </form>
    </DialogContent>
  );
}
