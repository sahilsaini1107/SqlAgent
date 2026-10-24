/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin for production builds; unset in dev (the Vite proxy is used). */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
