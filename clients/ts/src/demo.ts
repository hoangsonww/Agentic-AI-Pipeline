import { AgenticAIClient } from "./client.js";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const prompt = process.argv.slice(2).join(" ") || "Build a competitive briefing on ACME Robotics and draft a short outreach email.";

(async () => {
  const client = new AgenticAIClient({ baseUrl: BASE });
  const { chat_id } = await client.newChat();
  process.stdout.write("\\n--- Streaming ---\\n");
  const res = await client.chatStream({
    chat_id,
    message: prompt,
    onToken: (t) => process.stdout.write(t)
  });
  process.stdout.write("\\n\\n--- Done ---\\n");
  console.log("chat_id:", res.chat_id);
})();
