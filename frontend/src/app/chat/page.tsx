import { redirect } from "next/navigation";
import { auth, currentUser } from "@clerk/nextjs/server";
import { ChatLayout } from "@/components/chat/chat-layout";
import { Sidebar } from "@/components/chat/sidebar";

export default async function ChatPage() {
  const { userId } = auth();

  if (!userId) {
    redirect("/sign-in");
  }

  // Get user info
  const user = await currentUser();

  return (
    <ChatLayout>
      <Sidebar />
      <div className="flex-1 flex flex-col items-center justify-center bg-muted/30">
        <div className="text-center max-w-2xl mx-auto p-8">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center mx-auto mb-6 shadow-lg">
            <svg
              className="w-10 h-10 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 6V4m0 16v-2m6-6h2M4 12H6m12.778-6.778l-1.414 1.414M6.636 17.364l-1.414 1.414m12.728 0l-1.414-1.414M6.636 6.636L5.222 5.222M16 12a4 4 0 11-8 0 4 4 0 018 0z"
              />
            </svg>
          </div>
          <h1 className="text-4xl font-bold mb-3">
            مرحباً {user?.firstName || user?.username || "بك"} 👋
          </h1>
          <p className="text-muted-foreground text-lg mb-8">
            منصة الوكلاء الأذكياء العربية. اختر محادثة من القائمة أو ابدأ محادثة جديدة.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-xl mx-auto">
            <a
              href="/chat/new"
              className="p-6 rounded-xl border bg-card hover:shadow-md hover:border-primary/50 transition-all cursor-pointer block"
            >
              <div className="text-3xl mb-3">💬</div>
              <h3 className="font-semibold mb-1">ابدأ محادثة جديدة</h3>
              <p className="text-sm text-muted-foreground">
                تحدث مع أحد الوكلاء الأذكياء
              </p>
            </a>
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
                {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
              </span>
            </p>
          </div>
        </div>
      </div>
    </ChatLayout>
  );
}
