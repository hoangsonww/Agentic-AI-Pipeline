from locust import HttpUser, task, between
import json

class AgentUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def chat(self):
        with self.client.get("/api/new_chat", name="new_chat", catch_response=True) as r:
            if r.status_code != 200:
                r.failure("new_chat failed")
                return
            chat_id = r.json().get("chat_id")

        payload = {"chat_id": chat_id, "message": "Give me a 2-bullet summary of AMR vendors."}
        with self.client.post("/api/chat", json=payload, name="chat_stream", stream=True, catch_response=True) as r:
            ok = False
            try:
                for block in r.iter_lines():
                    if not block:
                        continue
                    if block.startswith(b"event: done"):
                        ok = True
                        break
            except Exception:
                pass
            if ok:
                r.success()
            else:
                r.failure("stream did not finish")
