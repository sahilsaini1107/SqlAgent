import { useEffect } from "react";

export interface Hotkey {
  /** e.g. "mod+k", "mod+shift+o", "/" — `mod` is Ctrl on Windows/Linux and ⌘ on macOS. */
  combo: string;
  handler: () => void;
  /** Fire even while typing in an input. */
  allowInInput?: boolean;
}

export const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const modKey = isMac ? "⌘" : "Ctrl";

function matches(event: KeyboardEvent, combo: string): boolean {
  const parts = combo.toLowerCase().split("+");
  const key = parts[parts.length - 1];
  const wantMod = parts.includes("mod");
  const wantShift = parts.includes("shift");
  const mod = isMac ? event.metaKey : event.ctrlKey;
  return event.key.toLowerCase() === key && mod === wantMod && event.shiftKey === wantShift && !event.altKey;
}

export function useHotkeys(hotkeys: Hotkey[]): void {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        !!target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));
      for (const hotkey of hotkeys) {
        if (!matches(event, hotkey.combo)) continue;
        if (typing && !hotkey.allowInInput) continue;
        event.preventDefault();
        hotkey.handler();
        return;
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [hotkeys]);
}
