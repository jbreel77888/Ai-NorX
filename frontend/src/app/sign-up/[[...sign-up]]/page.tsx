import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background-weak">
      <div className="w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-accent-strong flex items-center justify-center mx-auto mb-4 shadow-01">
            <span className="text-white font-bold text-xl">N</span>
          </div>
          <h1 className="text-2xl font-semibold mb-1 text-text-05">
            Ai NorX
          </h1>
          <p className="text-text-03 text-sm">
            انضم إلى منصة الوكلاء الأذكياء
          </p>
        </div>
        <div className="bg-background-strong rounded-xl shadow-01 p-6">
          <SignUp
            appearance={{
              elements: {
                card: "shadow-none border-0",
                headerTitle: "text-text-05",
                headerSubtitle: "text-text-03",
                formButtonPrimary:
                  "bg-accent-strong hover:bg-accent-strong/90 text-sm",
                socialButtonsBlockButton:
                  "border-border-01 hover:bg-background-weak text-text-05 rounded-lg",
                formFieldInput:
                  "border-border-01 rounded-lg bg-background-strong text-text-05",
                footerActionLink: "text-accent-weak hover:text-accent-strong",
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}
