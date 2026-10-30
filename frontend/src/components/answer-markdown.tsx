"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders a model answer as Markdown, turning [n] markers into citation chips.
 * react-markdown never renders raw HTML and sanitises link URLs, so model output can't inject markup.
 */
export function AnswerMarkdown({
  text,
  validCitations,
  onCite,
}: {
  text: string;
  validCitations: Set<number>;
  onCite: (n: number) => void;
}) {
  // [3] -> [3](#cite-3) so the Markdown parser hands us each marker as a link we can render as a chip.
  const withLinks = text.replace(/\[(\d+)\](?!\()/g, (match, n) => (validCitations.has(Number(n)) ? `[${n}](#cite-${n})` : match));
  return (
    <div className="prose-answer space-y-3 text-sm leading-relaxed text-slate-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const cite = href?.match(/^#cite-(\d+)$/);
            if (cite) {
              const n = Number(cite[1]);
              return (
                <button
                  type="button"
                  onClick={() => onCite(n)}
                  className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-indigo-100 px-1 align-text-top text-xs font-semibold text-indigo-700 hover:bg-indigo-200"
                  aria-label={`Show source ${n}`}
                >
                  {n}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-600 underline">
                {children}
              </a>
            );
          },
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          h1: ({ children }) => <h3 className="font-semibold">{children}</h3>,
          h2: ({ children }) => <h3 className="font-semibold">{children}</h3>,
          h3: ({ children }) => <h4 className="font-semibold">{children}</h4>,
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="min-w-full border border-slate-200 text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="border border-slate-200 bg-slate-50 px-2 py-1 text-left">{children}</th>,
          td: ({ children }) => <td className="border border-slate-200 px-2 py-1">{children}</td>,
          code: ({ children }) => <code className="rounded bg-slate-100 px-1 font-mono text-xs">{children}</code>,
        }}
      >
        {withLinks}
      </ReactMarkdown>
    </div>
  );
}
