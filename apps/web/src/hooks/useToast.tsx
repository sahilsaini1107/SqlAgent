import { createContext, useCallback, useContext, useState } from "react";

import { IconCheck } from "../components/Icons";

interface Toast {
  id: number;
  text: string;
}

const ToastContext = createContext<(text: string) => void>(() => undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((text: string) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev.slice(-2), { id, text }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 2200);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-6 z-[70] flex flex-col items-center gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="animate-pop flex items-center gap-2 rounded-full border border-white/10 bg-zinc-900/90 px-4 py-2 text-sm text-white shadow-2xl backdrop-blur-xl"
          >
            <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-500/20 text-emerald-400">
              <IconCheck size={13} strokeWidth={2.5} />
            </span>
            {toast.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

export function useCopy() {
  const toast = useToast();
  return useCallback(
    async (text: string, label = "Copied to clipboard") => {
      try {
        await navigator.clipboard.writeText(text);
        toast(label);
      } catch {
        toast("Couldn't access the clipboard");
      }
    },
    [toast],
  );
}
