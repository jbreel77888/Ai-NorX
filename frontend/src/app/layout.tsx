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
          colorPrimary: "#5b21b6",
          colorText: "#1a1a1a",
          colorBackground: "#ffffff",
          colorInputBackground: "#ffffff",
          colorInputText: "#1a1a1a",
          fontFamily: "'IBM Plex Sans Arabic', 'Inter', system-ui, sans-serif",
        },
        elements: {
          formButtonPrimary:
            "bg-[#5b21b6] hover:bg-[#5b21b6]/90 text-sm normal-case",
          card: "shadow-none border border-[var(--border-01)] rounded-xl",
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
            href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap"
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
