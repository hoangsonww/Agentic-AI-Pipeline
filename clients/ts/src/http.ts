export async function httpJson(url: string, init?: RequestInit): Promise<any> {
  const r = await fetch(url, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers||{}) } });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(\`HTTP \${r.status}: \${text}\`);
  }
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) return r.json();
  return r.text();
}

export async function streamSSE(
  url: string,
  init: RequestInit & { onEvent: (ev: { event: string; data: string }) => void }
): Promise<void> {
  const resp = await fetch(url, init);
  if (!resp.ok || !resp.body) throw new Error(\`SSE HTTP \${resp.status}\`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i).trim();
      buf = buf.slice(i + 2);
      const ev = /event:(.*)/.exec(block)?.[1]?.trim() || "message";
      const data = /data:(.*)/s.exec(block)?.[1]?.trim() || "";
      init.onEvent({ event: ev, data });
    }
  }
}
