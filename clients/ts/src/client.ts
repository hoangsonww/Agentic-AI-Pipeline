export type ChatId = string;

export interface AgenticOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export class AgenticAIClient {
  private base: string;
  private f: typeof fetch;

  constructor(opts: AgenticOptions = {}) {
    this.base = (opts.baseUrl ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
    this.f = opts.fetchImpl ?? fetch;
  }

  async newChat(): Promise<{ chat_id: ChatId }> {
    const r = await this.f(\`\${this.base}/api/new_chat\`);
    if (!r.ok) throw new Error(\`newChat failed: \${r.status}\`);
    return r.json();
  }

  async ingest(text: string, metadata: Record<string, unknown> = {}): Promise<{ ok: boolean; id: string }> {
    const r = await this.f(\`\${this.base}/api/ingest\`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, metadata })
    });
    if (!r.ok) throw new Error(\`ingest failed: \${r.status}\`);
    return r.json();
  }

  async feedback(chat_id: ChatId, rating: number, comment?: string, message_id?: number): Promise<{ ok: boolean }> {
    const r = await this.f(\`\${this.base}/api/feedback\`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id, rating, comment, message_id })
    });
    if (!r.ok) throw new Error(\`feedback failed: \${r.status}\`);
    return r.json();
  }

  /**
   * Stream a chat completion via SSE-like response.
   * Calls onToken for each "token" event. Resolves when "done" is received.
   */
  async chatStream(args: {
    chat_id?: ChatId;
    message: string;
    onToken: (chunk: string) => void;
  }): Promise<{ chat_id: ChatId }> {
    const r = await this.f(\`\${this.base}/api/chat\`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: args.chat_id, message: args.message })
    });
    if (!r.ok || !r.body) {
      throw new Error(\`chatStream failed: \${r.status}\`);
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    let finalChatId: ChatId | undefined = args.chat_id;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\\n\\n").filter(Boolean);
      // Process all full events; keep tail in buf
      for (let i = 0; i < parts.length - 1; i++) {
        const block = parts[i];
        const lines = block.split("\\n");
        const ev = (lines.find(l => l.startsWith("event:")) || "").slice(6).trim();
        const data = (lines.find(l => l.startsWith("data:")) || "").slice(5);
        if (ev === "token") {
          args.onToken(data);
        } else if (ev === "done") {
          try {
            const meta = JSON.parse(data);
            finalChatId = meta.chat_id ?? finalChatId;
          } catch {}
        }
      }
      buf = parts[parts.length - 1] || "";
    }

    // Flush last block if it contains a done event
    if (buf.includes("event: done")) {
      const line = buf.split("\\n").find(l => l.startsWith("data:")) || "";
      try {
        const meta = JSON.parse(line.slice(5));
        finalChatId = meta.chat_id ?? finalChatId;
      } catch {}
    }
    if (!finalChatId) throw new Error("No chat_id returned by server.");
    return { chat_id: finalChatId };
  }
}
