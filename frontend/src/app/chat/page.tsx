import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import { ChatLayout } from "@/components/chat/chat-layout";
import { Sidebar } from "@/components/chat/sidebar";

export default async function ChatPage() {
  const { userId } = auth();

  if (!userId) {
    redirect("/sign-in");
  }

  return (
    <ChatLayout>
      <Sidebar />
      <div className="flex-1 flex items-center justify-center bg-muted/30">
        <div className="text-center max-w-2xl mx-auto p-8">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center mx-auto mb-6">
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
            مرحباً بك في Ai NorX
          </h1>
          <p className="text-muted-foreground text-lg mb-8">
            منصة الوكلاء الأذكياء العربية. اختر محادثة من القائمة أو ابدأ محادثة جديدة.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl border bg-card hover:shadow-md transition-shadow cursor-pointer">
              <div className="text-2xl mb-2">💬</div>
              <h3 className="font-semibold mb-1">ابدأ محادثة جديدة</h3>
              <p className="text-sm text-muted-foreground">
                تحدث مع أحد الوكلاء الأذكياء
              </p>
            </div>
            <div className="p-4 rounded-xl border bg-card hover:shadow-md transition-shadow cursor-pointer">
              <div className="text-2xl mb-2">🤖</div>
              <h3 className="font-semibold mb-1">أنشئ وكيل جديد</h3>
              <p className="text-sm text-muted-foreground">
                خصص وكيلك الذكي الخاص
              </p>
            </div>
          </div>
        </div>
      </div>
    </ChatLayout>
  );
}
