import type { Metadata } from "next";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { QueryProvider } from "@/lib/providers/query-provider";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";

export const metadata: Metadata = {
  title: "Ai NorX - منصة الوكلاء الأذكياء",
  description: "منصة سحابية عربية للوكلاء الأذكياء على غرار Manus AI و Z.ai",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider
      appearance={{
        variables: {
          colorPrimary: "#2563eb",
          colorText: "#0f172a",
          colorBackground: "#ffffff",
          colorInputBackground: "#ffffff",
          colorInputText: "#0f172a",
          fontFamily: "'IBM Plex Sans Arabic', 'Cairo', system-ui, sans-serif",
        },
        elements: {
          formButtonPrimary:
            "bg-blue-600 hover:bg-blue-700 text-sm normal-case",
          card: "shadow-xl rounded-2xl border-0",
        },
      }}
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      afterSignInUrl="/chat"
      afterSignUpUrl="/chat"
    >
      <html lang="ar" dir="rtl" suppressHydrationWarning>
        <head>
          <link
            href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&family=Cairo:wght@300;400;500;600;700;800&family=Amiri:wght@400;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
            rel="stylesheet"
          />
        </head>
        <body className="font-sans antialiased">
          <QueryProvider>
            <TooltipProvider>
              {children}
              <Toaster />
            </TooltipProvider>
          </QueryProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
