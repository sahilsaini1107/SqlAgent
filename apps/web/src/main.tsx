import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Self-hosted fonts (no external origin, so a strict CSP is possible). Only the weights the UI
// actually uses — Inter 400/500/600/700 and JetBrains Mono 400/500/600.
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/600.css";

import App from "./App.tsx";
import { ToastProvider } from "./hooks/useToast";
import "./index.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
);
