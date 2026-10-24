import { useEffect, useState } from "react";

interface Health {
  status: string;
  version: string;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/health")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 text-slate-900">
      <h1 className="text-2xl font-semibold">SQL Agent</h1>
      {health && (
        <p className="text-sm text-emerald-600">
          API {health.status} · v{health.version}
        </p>
      )}
      {error && <p className="text-sm text-red-600">API unreachable: {error}</p>}
      {!health && !error && <p className="text-sm text-slate-500">Checking API…</p>}
    </main>
  );
}
