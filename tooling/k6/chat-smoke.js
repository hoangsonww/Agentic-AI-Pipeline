import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 5,
  duration: "30s"
};

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";

export default function () {
  let r = http.get(\`\${BASE}/api/new_chat\`);
  check(r, { "new_chat 200": (res) => res.status === 200 });

  const payload = JSON.stringify({ text: "kb doc from k6", metadata: { k6: true } });
  const headers = { "Content-Type": "application/json" };
  r = http.post(\`\${BASE}/api/ingest\`, payload, { headers });
  check(r, { "ingest 200": (res) => res.status === 200 });

  r = http.post(\`\${BASE}/api/feedback\`, JSON.stringify({ chat_id: "k6", rating: 1 }), { headers });
  check(r, { "feedback 200": (res) => res.status === 200 });

  sleep(1);
}
