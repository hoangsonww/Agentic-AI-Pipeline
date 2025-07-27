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
}
