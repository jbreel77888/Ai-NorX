"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, ArrowLeft, Loader2, User, Bot } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { conversationsApi, agentsApi, Message } from "@/lib/api";
import { Sidebar } from "@/components/chat/sidebar";
import { ChatLayout } from "@/components/chat/chat-layout";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export default function ConversationPage() {
  const params = useParams();
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [token, setToken] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
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
  }, [token, conversationId, agent, queryClient]);

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

  // Show loading state while Clerk loads
  if (!isLoaded) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!isSignedIn) {
    return null;
  }

  return (
    <ChatLayout>
      <Sidebar />
      <div className="flex-1 flex flex-col h-full">
        <header className="border-b p-4 flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/chat")}
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="flex-1">
            <h2 className="font-semibold">
              {conversation?.title || "محادثة"}
            </h2>
            {agent && (
              <p className="text-xs text-muted-foreground">
                {agent.name} · {agent.llm_model}
              </p>
            )}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {messages.length === 0 && !streamingContent && (
            <div className="text-center py-12 text-muted-foreground">
              <Bot className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>ابدأ المحادثة بكتابة رسالة أدناه</p>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {streamingContent && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 bg-muted rounded-2xl p-4">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {streamingContent}
                  </ReactMarkdown>
                </div>
                <span className="inline-block w-2 h-4 bg-primary animate-pulse mt-2" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {error && (
          <div className="px-4 py-2 bg-destructive/10 text-destructive text-sm text-center">
            {error}
          </div>
        )}

        <div className="border-t p-4">
          <div className="flex gap-2 items-end max-w-3xl mx-auto">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="اكتب رسالتك هنا..."
              disabled={isStreaming}
              className="min-h-[44px] max-h-32 resize-none"
              rows={1}
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              size="icon"
              className="h-11 w-11 shrink-0"
            >
              {isStreaming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </ChatLayout>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
          isUser
            ? "bg-primary"
            : "bg-gradient-to-br from-blue-500 to-purple-600"
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-white" />
        )}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl p-4",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
        <div
          className={cn(
            "text-xs mt-2 opacity-70",
            isUser ? "text-primary-foreground" : "text-muted-foreground"
          )}
        >
          {new Date(message.created_at).toLocaleTimeString("ar-SA")}
        </div>
      </div>
    </div>
  );
}
