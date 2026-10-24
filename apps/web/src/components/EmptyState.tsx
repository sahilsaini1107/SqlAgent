import { IconBolt, IconChart, IconCode, IconShield, IconSparkles, IconTable, IconWand, Logo } from "./Icons";

export const EXAMPLES = [
  { icon: IconChart, tag: "Revenue", prompt: "Monthly revenue in USD for 2025 with month-over-month growth" },
  { icon: IconTable, tag: "Ranking", prompt: "Best-selling product in each department by revenue" },
  { icon: IconBolt, tag: "Operations", prompt: "Which carriers have the highest late-delivery rate?" },
  { icon: IconCode, tag: "Retention", prompt: "Repeat purchase rate by acquisition channel" },
];

const PILLARS = [
  { icon: IconShield, text: "Read-only by design" },
  { icon: IconWand, text: "Self-repairing SQL" },
  { icon: IconSparkles, text: "Explains every query" },
];

interface Props {
  onExample: (prompt: string) => void;
}

export function EmptyState({ onExample }: Props) {
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full max-w-3xl flex-col items-center justify-center px-6 py-10 text-center">
        <div className="animate-pop relative mb-7">
          <div className="relative">
            <Logo size={64} />
          </div>
        </div>

        <h1 className="animate-fade-up text-4xl font-bold tracking-tight sm:text-5xl">
          Talk to your <span className="text-accent-600 dark:text-accent-400">data</span>.
        </h1>
        <p
          className="animate-fade-up mt-3 max-w-md text-[15px] leading-relaxed text-zinc-500 dark:text-zinc-400"
          style={{ animationDelay: "80ms" }}
        >
          Ask in plain English. Get validated, read-only SQL, live results, and an explanation of every step.
        </p>

        <div className="animate-fade-up mt-5 flex flex-wrap justify-center gap-2" style={{ animationDelay: "140ms" }}>
          {PILLARS.map(({ icon: Icon, text }) => (
            <span
              key={text}
              className="flex items-center gap-1.5 rounded-full border border-black/5 bg-white/50 px-3 py-1 text-[11px] font-medium text-zinc-500 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-zinc-400"
            >
              <Icon size={12} className="text-zinc-400" /> {text}
            </span>
          ))}
        </div>

        <div className="mt-9 grid w-full gap-3 sm:grid-cols-2">
          {EXAMPLES.map(({ icon: Icon, tag, prompt }, i) => (
            <button
              key={prompt}
              onClick={() => onExample(prompt)}
              style={{ animationDelay: `${200 + i * 70}ms` }}
              className="animate-fade-up group relative overflow-hidden rounded-2xl border border-black/5 bg-white/60 p-4 text-left backdrop-blur-xl transition duration-300 hover:border-accent-400/50 hover:shadow-md dark:border-white/[0.06] dark:bg-white/[0.03]"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="grid h-8 w-8 place-items-center rounded-xl bg-accent-500/10 text-accent-500 transition group-hover:scale-110 dark:text-accent-300">
                  <Icon size={16} />
                </span>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">{tag}</span>
              </div>
              <p className="text-sm font-medium text-zinc-700 dark:text-zinc-200">{prompt}</p>
              <span className="mt-2 block text-[11px] text-zinc-400 opacity-0 transition group-hover:opacity-100">
                Run it →
              </span>
            </button>
          ))}
        </div>

      </div>
    </div>
  );
}
