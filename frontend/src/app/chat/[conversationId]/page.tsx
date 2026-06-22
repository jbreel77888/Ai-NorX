"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth, useUser } from "@clerk/nextjs";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Send,
  Loader2,
  Bot,
  Square,
  ChevronDown,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { conversationsApi, agentsApi, Message } from "@/lib/api";
import { ChatLayout } from "@/components/chat/chat-layout";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export default function ConversationPage() {
  const params = useParams();
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { user } = useUser();
  const [token, setToken] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const queryClient = useQueryClient();

  const conversationId = params?.conversationId as string;

  // Get token
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

  // Redirect if not signed in
  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      router.push("/sign-in");
    }
  }, [isLoaded, isSignedIn, router]);

  // Load conversation
  const { data: conversation } = useQuery({
    queryKey: ["conversation", conversationId, token],
    queryFn: () => conversationsApi.get(conversationId, token),
    enabled: !!token && !!conversationId,
    retry: false,
  });

  const { data: dbMessages } = useQuery({
    queryKey: ["messages", conversationId, token],
    queryFn: () => conversationsApi.messages(conversationId, token),
    enabled: !!token && !!conversationId,
    retry: false,
  });

  useEffect(() => {
    if (dbMessages) setMessages(dbMessages);
  }, [dbMessages]);

  const { data: agent } = useQuery({
    queryKey: ["agent", conversation?.agent_id, token],
    queryFn: () => agentsApi.get(conversation!.agent_id!, token),
    enabled: !!token && !!conversation?.agent_id,
    retry: false,
  });

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Setup WebSocket
  useEffect(() => {
    if (!token) return;

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const wsUrl = apiBaseUrl.replace("http", "ws") + "/api/v1/chat/ws";

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "auth", token }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "auth_success":
          break;
        case "text":
          setStreamingContent((prev) => prev + data.content);
          break;
        case "user_message_saved":
          setMessages((prev) => [
            ...prev,
            {
              id: data.message_id,
              role: "user",
              content: input,
              tool_calls: [],
              input_tokens: 0,
              output_tokens: 0,
              cost: 0,
              created_at: new Date().toISOString(),
            },
          ]);
          setInput("");
          break;
        case "assistant_message_saved":
          setMessages((prev) => [
            ...prev,
            {
              id: data.message_id,
              role: "assistant",
              content: streamingContent,
              tool_calls: [],
              model_used: agent?.llm_model,
              provider: agent?.llm_provider,
              input_tokens: data.usage?.input_tokens || 0,
              output_tokens: data.usage?.output_tokens || 0,
              cost: data.usage?.cost || 0,
              created_at: new Date().toISOString(),
            },
          ]);
          setStreamingContent("");
          setIsStreaming(false);
          queryClient.invalidateQueries({
            queryKey: ["messages", conversationId],
          });
          queryClient.invalidateQueries({ queryKey: ["conversations"] });
          break;
        case "error":
          setError(data.content);
          setIsStreaming(false);
          setStreamingContent("");
          break;
        case "done":
          setIsStreaming(false);
          break;
      }
    };

    ws.onerror = () => {
      setError("فشل الاتصال بالخادم");
      setIsStreaming(false);
    };

    return () => {
      ws.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, conversationId, agent]);

  const handleSend = () => {
    if (!input.trim() || isStreaming || !agent) return;
    setError(null);
    setIsStreaming(true);
    setStreamingContent("");

    wsRef.current?.send(
      JSON.stringify({
        type: "chat",
        content: input.trim(),
        agent_id: agent.id,
        conversation_id: conversationId,
      })
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isLoaded || !isSignedIn) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const userName = user?.firstName || user?.username || "أهلاً";

  return (
    <ChatLayout>
      {/* Chat Header */}
      <header className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-background/80 backdrop-blur">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="font-medium text-sm">NorX</div>
            <div className="text-[11px] text-muted-foreground">
              {agent?.llm_model || "Llama 3.1 70B"}
            </div>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="text-muted-foreground gap-1">
          <span className="text-xs">نموذج</span>
          <ChevronDown className="w-3 h-3" />
        </Button>
      </header>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {messages.length === 0 && !streamingContent && (
            <div className="text-center py-12">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center mx-auto mb-4 shadow-lg">
                <Bot className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-2xl font-semibold mb-2">
                مرحباً، {userName} 👋
              </h1>
              <p className="text-muted-foreground mb-8">
                أنا NorX، وكيلك الذكي العام. كيف يمكنني مساعدتك اليوم؟
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-xl mx-auto">
                <SuggestionCard
                  text="✍️ اكتب لي مقالاً عن الذكاء الاصطناعي"
                  onClick={() => setInput("اكتب لي مقالاً عن الذكاء الاصطناعي")}
                />
                <SuggestionCard
                  text="💻 ساعدني في كتابة كود Python"
                  onClick={() => setInput("ساعدني في كتابة كود Python")}
                />
                <SuggestionCard
                  text="📊 حلّل لي هذه البيانات"
                  onClick={() => setInput("حلّل لي هذه البيانات")}
                />
                <SuggestionCard
                  text="🌐 اترجم لي نص للإنجليزية"
                  onClick={() => setInput("اترجم لي نص للإنجليزية")}
                />
              </div>
            </div>
          )}

          <div className="space-y-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {streamingContent && (
              <div className="flex gap-3 animate-in">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1 pt-1">
                  <div className="prose-chat max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {streamingContent}
                    </ReactMarkdown>
                  </div>
                  <div className="flex gap-1 mt-2">
                    <span className="w-1.5 h-1.5 bg-primary rounded-full typing-dot" />
                    <span className="w-1.5 h-1.5 bg-primary rounded-full typing-dot" />
                    <span className="w-1.5 h-1.5 bg-primary rounded-full typing-dot" />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="px-4 py-2 bg-destructive/10 text-destructive text-sm text-center">
          {error}
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-border bg-background p-4">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end gap-2 bg-secondary/50 rounded-2xl border border-border focus-within:border-primary/50 p-2">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="اكتب رسالتك إلى NorX..."
              disabled={isStreaming}
              className="min-h-[24px] max-h-[200px] resize-none bg-transparent border-0 focus-visible:ring-0 px-2 py-1.5"
              rows={1}
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              size="icon"
              className="h-8 w-8 shrink-0 rounded-lg"
            >
              {isStreaming ? (
                <Square className="w-3 h-3 fill-current" />
              ) : (
                <Send className="w-3.5 h-3.5" />
              )}
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground/60 text-center mt-1.5">
            قد ينتج NorX معلومات غير دقيقة. تحقق دائماً من المعلومات المهمة.
          </p>
        </div>
      </div>
    </ChatLayout>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end animate-in">
        <div className="max-w-[80%] bg-primary text-primary-foreground rounded-2xl rounded-bl-md px-4 py-2.5">
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 animate-in">
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center shrink-0">
        <Bot className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1 pt-0.5">
        <div className="prose-chat max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

function SuggestionCard({ text, onClick }: { text: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="p-3 rounded-xl border border-border bg-background hover:bg-secondary/50 hover:border-primary/30 text-right text-sm transition-colors"
    >
      {text}
    </button>
  );
}
