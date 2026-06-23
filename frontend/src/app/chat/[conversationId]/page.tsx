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
  Search,
  Globe,
  ExternalLink,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { conversationsApi, agentsApi, Message } from "@/lib/api";
import { ChatLayout } from "@/components/chat/chat-layout";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface ToolExecution {
  tool: string;
  arguments: string;
  call_id: string;
  status: "running" | "done" | "error";
  result?: string;
  citations?: any[];
  execution_time_ms?: number;
}

interface ChatMessage {
  id: string;
  role: string;
  content: string;
  tool_calls?: any[];
  citations?: any[];
  created_at: string;
}

export default function ConversationPage() {
  const params = useParams();
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { user } = useUser();
  const [token, setToken] = useState("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeTools, setActiveTools] = useState<Record<string, ToolExecution>>({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const queryClient = useQueryClient();

  const conversationId = params?.conversationId as string;

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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, activeTools]);

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

        case "tool_call_start":
          setActiveTools((prev) => ({
            ...prev,
            [data.call_id]: {
              tool: data.tool,
              arguments: data.arguments,
              call_id: data.call_id,
              status: "running",
            },
          }));
          break;

        case "tool_call_end":
          setActiveTools((prev) => ({
            ...prev,
            [data.call_id]: {
              ...prev[data.call_id],
              status: data.success ? "done" : "error",
              result: data.result_preview,
              citations: data.citations || [],
              execution_time_ms: data.execution_time_ms,
            },
          }));
          // Also collect citations for the final message
          if (data.citations?.length) {
            setStreamingCitations((prev) => [...prev, ...data.citations]);
          }
          break;

        case "user_message_saved":
          setMessages((prev) => [
            ...prev,
            {
              id: data.message_id,
              role: "user",
              content: input,
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
              citations: data.citations || streamingCitations,
              created_at: new Date().toISOString(),
            },
          ]);
          setStreamingContent("");
          setStreamingCitations([]);
          setActiveTools({});
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
          setActiveTools({});
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
    setStreamingCitations([]);
    setActiveTools({});

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
  const activeToolList = Object.values(activeTools);

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
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Search className="w-3 h-3" />
          <span>بحث ويب مفعّل</span>
        </div>
      </header>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {messages.length === 0 && !streamingContent && activeToolList.length === 0 && (
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
                  text="🔍 ابحث عن آخر أخبار الذكاء الاصطناعي"
                  onClick={() => setInput("ابحث عن آخر أخبار الذكاء الاصطناعي في 2026")}
                />
                <SuggestionCard
                  text="✍️ اكتب لي مقالاً عن التقنية"
                  onClick={() => setInput("اكتب لي مقالاً قصيراً عن التقنية")}
                />
                <SuggestionCard
                  text="💻 ساعدني في كتابة كود Python"
                  onClick={() => setInput("ساعدني في كتابة كود Python لقراءة ملف CSV")}
                />
                <SuggestionCard
                  text="🌐 ما هو الطقس في الرياض اليوم؟"
                  onClick={() => setInput("ما هو الطقس في الرياض اليوم؟")}
                />
              </div>
            </div>
          )}

          <div className="space-y-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Active tool executions */}
            {activeToolList.length > 0 && (
              <div className="space-y-2">
                {activeToolList.map((tool) => (
                  <ToolExecutionCard key={tool.call_id} tool={tool} />
                ))}
              </div>
            )}

            {/* Streaming response */}
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

            {/* Citations from streaming */}
            {streamingCitations.length > 0 && !streamingContent && (
              <CitationsList citations={streamingCitations} />
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>

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
            NorX يمكنه البحث في الويب وجلب المعلومات. تحقق دائماً من المعلومات المهمة.
          </p>
        </div>
      </div>
    </ChatLayout>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
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
      <div className="flex-1 pt-0.5 min-w-0">
        <div className="prose-chat max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Show tool calls if any */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {message.tool_calls.map((tc: any, i: number) => (
              <div
                key={i}
                className="text-xs bg-secondary/60 rounded-lg p-2 border border-border"
              >
                <div className="flex items-center gap-1.5 font-medium text-muted-foreground">
                  {tc.name === "web_search" && <Search className="w-3 h-3" />}
                  {tc.name === "web_fetch" && <Globe className="w-3 h-3" />}
                  <span>{tc.name}</span>
                  {tc.execution_time_ms && (
                    <span className="text-muted-foreground/60">
                      ({tc.execution_time_ms}ms)
                    </span>
                  )}
                </div>
                <div className="text-muted-foreground mt-0.5 truncate">
                  {tc.arguments?.query || tc.arguments?.url || JSON.stringify(tc.arguments)}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Show citations if any */}
        {message.citations && message.citations.length > 0 && (
          <CitationsList citations={message.citations} />
        )}
      </div>
    </div>
  );
}

function ToolExecutionCard({ tool }: { tool: ToolExecution }) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = tool.status === "running";

  let args: any = {};
  try {
    args = typeof tool.arguments === "string" ? JSON.parse(tool.arguments) : tool.arguments;
  } catch {}

  return (
    <div className="flex gap-3 animate-in">
      <div
        className={cn(
          "w-7 h-7 rounded-full flex items-center justify-center shrink-0",
          isRunning
            ? "bg-blue-500"
            : tool.status === "done"
            ? "bg-green-500"
            : "bg-destructive"
        )}
      >
        {isRunning ? (
          <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
        ) : tool.tool === "web_search" ? (
          <Search className="w-3.5 h-3.5 text-white" />
        ) : (
          <Globe className="w-3.5 h-3.5 text-white" />
        )}
      </div>
      <div className="flex-1 pt-1">
        <div className="bg-secondary/50 rounded-lg border border-border overflow-hidden">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between p-2.5 hover:bg-secondary/70"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">
                {tool.tool === "web_search" ? "🔍 البحث في الويب" : "🌐 جلب محتوى ويب"}
              </span>
              {isRunning && (
                <span className="text-[11px] text-blue-500">جارٍ التنفيذ...</span>
              )}
              {tool.status === "done" && (
                <span className="text-[11px] text-green-600">
                  اكتمل {tool.execution_time_ms && `(${tool.execution_time_ms}ms)`}
                </span>
              )}
            </div>
            <ChevronDown
              className={cn(
                "w-4 h-4 text-muted-foreground transition-transform",
                expanded && "rotate-180"
              )}
            />
          </button>

          <div className="px-2.5 pb-2.5 text-xs">
            <div className="text-muted-foreground mb-1">الاستعلام:</div>
            <div className="font-mono bg-background/50 rounded p-1.5 mb-2">
              {args.query || args.url || JSON.stringify(args)}
            </div>

            {tool.result && (
              <>
                <div className="text-muted-foreground mb-1">النتيجة:</div>
                <div className="bg-background/50 rounded p-1.5 max-h-32 overflow-y-auto text-muted-foreground">
                  {tool.result}
                </div>
              </>
            )}

            {tool.citations && tool.citations.length > 0 && (
              <>
                <div className="text-muted-foreground mb-1 mt-2">
                  المصادر ({tool.citations.length}):
                </div>
                <div className="space-y-1">
                  {tool.citations.slice(0, 3).map((c: any, i: number) => (
                    <a
                      key={i}
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-primary hover:underline text-[11px]"
                    >
                      <ExternalLink className="w-2.5 h-2.5" />
                      <span className="truncate">{c.title}</span>
                    </a>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function CitationsList({ citations }: { citations: any[] }) {
  if (!citations?.length) return null;

  // Deduplicate by URL
  const unique = Array.from(
    citations
      .filter((c) => c.url)
      .reduce((map, c) => {
        if (!map.has(c.url)) map.set(c.url, c);
        return map;
      }, new Map<string, any>())
      .values()
  ).slice(0, 8);

  if (!unique.length) return null;

  return (
    <div className="mt-3 pt-3 border-t border-border">
      <div className="text-xs font-medium text-muted-foreground mb-2">
        📚 المصادر ({unique.length})
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
        {unique.map((c: any, i: number) => (
          <a
            key={i}
            href={c.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-1.5 p-2 rounded-lg bg-secondary/40 hover:bg-secondary/70 border border-border text-xs group"
          >
            <span className="text-muted-foreground font-mono shrink-0">
              [{i + 1}]
            </span>
            <div className="min-w-0 flex-1">
              <div className="font-medium truncate group-hover:text-primary">
                {c.title || c.url}
              </div>
              {c.source && (
                <div className="text-muted-foreground text-[10px] truncate">
                  {c.source}
                </div>
              )}
            </div>
            <ExternalLink className="w-3 h-3 text-muted-foreground shrink-0 mt-0.5" />
          </a>
        ))}
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
