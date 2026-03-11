import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export function MarkdownContent({ content, className = "" }: MarkdownContentProps) {
  return (
    <div className={`max-w-none space-y-3 ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: ({ children, className: codeClassName, ...props }) => {
            const isInline = !codeClassName;
            return isInline ? (
              <code className="rounded bg-zinc-800 px-1 py-0.5 text-xs text-zinc-300" {...props}>
                {children}
              </code>
            ) : (
              <code className={`${codeClassName ?? ""} text-xs`} {...props}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="overflow-x-auto rounded bg-zinc-800 p-3 text-xs">{children}</pre>
          ),
          table: ({ children }) => (
            <table className="w-full border-collapse text-xs">{children}</table>
          ),
          th: ({ children }) => (
            <th className="border border-zinc-700 bg-zinc-800 px-2 py-1 text-left font-medium text-zinc-300">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-zinc-700 px-2 py-1 text-zinc-400">{children}</td>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              className="text-blue-400 hover:text-blue-300 no-underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          h1: ({ children }) => <h1 className="text-lg font-bold text-zinc-200">{children}</h1>,
          h2: ({ children }) => <h2 className="text-base font-semibold text-zinc-200">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold text-zinc-300">{children}</h3>,
          p: ({ children }) => <p className="text-zinc-400 leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-zinc-400">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-zinc-600 pl-3 text-zinc-500 italic">
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
