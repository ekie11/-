"""Заглушка модели для e2e: OpenAI-совместимый /chat/completions с фиксированным ответом."""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

ANSWER = {
    "found": [
        {
            "rule": "page.margins",
            "path": "left_mm",
            "value": 25,
            "quote": "левое — 25 мм",
        }
    ],
    "unsupported": [],
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not self.path.endswith("/chat/completions"):
            self.send_error(404)
            return
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": json.dumps(ANSWER)}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
