import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-900 dark:to-gray-800">
      <div className="w-full max-w-md p-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Ai NorX
          </h1>
          <p className="text-muted-foreground">
            منصة الوكلاء الأذكياء العربية
          </p>
        </div>
        <SignIn
          appearance={{
            elements: {
              card: "shadow-xl rounded-2xl border-0",
              headerTitle: "text-right",
              headerSubtitle: "text-right",
              formButtonPrimary: "bg-blue-600 hover:bg-blue-700",
              socialButtonsBlockButton: "rounded-lg",
              formFieldInput: "rounded-lg",
            },
          }}
        />
      </div>
    </div>
  );
}
