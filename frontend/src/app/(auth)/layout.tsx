import { BookOpenText } from "lucide-react";
import { Suspense } from "react";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm space-y-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="rounded-xl bg-indigo-600 p-2.5 text-white">
            <BookOpenText className="size-6" aria-hidden />
          </div>
          <div>
            <p className="text-lg font-semibold">KnowledgeHub AI</p>
            <p className="text-sm text-slate-500">Answers from your documents, with sources.</p>
          </div>
        </div>
        <Suspense>{children}</Suspense>
      </div>
    </main>
  );
}
