import { httpJson, streamSSE } from "./http.js";

export type ChatId = string;
export interface AgenticOptions { baseUrl?: string; fetchImpl?: typeof fetch; }

export class AgenticAIClient {
  private base: string;
  constructor(opts: AgenticOptions = {}) {
    this.base = (opts.baseUrl ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
  }

  async newChat() { return httpJson(\`\${this.base}/api/new_chat\`); }

  async ingest(text: string, metadata: Record<string, unknown> = {}) {
    return httpJson(\`\${this.base}/api/ingest\`, { method: "POST", body: JSON.stringify({ text, metadata }) });
  }

  async feedback(chat_id: string, rating: number, comment?: string, message_id?: number) {
    return httpJson(\`\${this.base}/api/feedback\`, { method: "POST", body: JSON.stringify({ chat_id, rating, comment, message_id }) });
  }

  async chatStream(args: { chat_id?: ChatId; message: string; onToken: (chunk: string) => void; }): Promise<{ chat_id: ChatId }> {
    let finalChat: ChatId | undefined = args.chat_id;
    await streamSSE(\`\${this.base}/api/chat\`, {
      method: "POST",
      body: JSON.stringify({ chat_id: args.chat_id, message: args.message }),
      onEvent: ({ event, data }) => {
        if (event === "token") args.onToken(data);
        if (event === "done") try { finalChat = JSON.parse(data).chat_id ?? finalChat; } catch {}
      }
    });
    if (!finalChat) throw new Error("No chat_id returned by server.");
    return { chat_id: finalChat };
  }

  // ----- Extended ingestion -----
  async ingestUrl(url: string, metadata: Record<string, unknown> = {}) {
    return httpJson(`${this.base}/api/ingest_url`, { method: "POST", body: JSON.stringify({ url, metadata }) });
  }

  async ingestFile(file: File | Blob, opts?: { filename?: string; tags?: string[] }) {
    const fd = new FormData();
    // @ts-ignore File has a name in browsers; for Blob provide filename option
    const fname = (file as any).name || opts?.filename || "upload";
    fd.append("file", file, fname);
    if (opts?.tags?.length) fd.append("tags", opts.tags.join(","));
    const r = await fetch(`${this.base}/api/ingest_file`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text().catch(()=>"")}`);
    return r.json();
  }

  // ----- Agentic Coding Pipeline -----
  async codingRun(args: { repo?: string | null; github?: string | null; jira?: string | null; task?: string | null }) {
    return httpJson(`${this.base}/api/coding/run`, { method: "POST", body: JSON.stringify(args) });
  }

  async codingStream(args: { repo?: string | null; github?: string | null; jira?: string | null; task?: string | null; onEvent: (ev: { event: string; data: string }) => void }) {
    await streamSSE(`${this.base}/api/coding/stream`, { method: "POST", body: JSON.stringify(args), onEvent: args.onEvent });
  }

  // ----- Agentic RAG Pipeline -----
  async ragNewSession(): Promise<{ session_id: string }> {
    return httpJson(`${this.base}/api/rag/new_session`);
  }

  async ragAskStream(args: { session_id?: string; question: string; onEvent: (ev: { event: string; data: string }) => void }) {
    await streamSSE(`${this.base}/api/rag/ask`, { method: "POST", body: JSON.stringify({ session_id: args.session_id, question: args.question }), onEvent: args.onEvent });
  }

  async ragIngestText(payload: { text?: string; url?: string; title?: string | null; tags?: string[] }) {
    return httpJson(`${this.base}/api/rag/ingest_text`, { method: "POST", body: JSON.stringify(payload) });
  }

  async ragIngestFile(file: File | Blob, opts?: { title?: string; tags?: string[] }) {
    const fd = new FormData();
    // @ts-ignore name may exist
    fd.append("file", file, (file as any).name || "upload");
    if (opts?.title) fd.append("title", opts.title);
    if (opts?.tags?.length) fd.append("tags", opts.tags.join(","));
    const r = await fetch(`${this.base}/api/rag/ingest_file`, { method: "POST", body: fd });
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text().catch(()=>"")}`);
    return r.json();
  }
}
