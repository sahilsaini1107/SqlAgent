import { useEffect, useState } from "react";

/** Reveal text word by word. Finishes in roughly a second and a half however long the text is. */
export function useTypewriter(text: string, enabled: boolean): { shown: string; done: boolean } {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    const total = text.split(/(\s+)/).length;
    const step = Math.max(1, Math.ceil(total / 60));
    setCount(0);
    const timer = setInterval(() => {
      setCount((c) => {
        if (c + step >= total) clearInterval(timer);
        return Math.min(total, c + step);
      });
    }, 24);
    return () => clearInterval(timer);
  }, [enabled, text]);

  if (!enabled) return { shown: text, done: true };
  const words = text.split(/(\s+)/);
  const done = count >= words.length;
  return { shown: done ? text : words.slice(0, count).join(""), done };
}
