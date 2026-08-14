import os
import json
from http.server import BaseHTTPRequestHandler
import requests
from render_lib import render_html_from_quote
import traceback


RENDER_TOKEN = os.environ.get("RENDER_TOKEN")


class handler(BaseHTTPRequestHandler):

    def _send_json(self, status_code, data):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):
        self._send_json(
            405,
            {
                "error": "Method Not Allowed",
                "message": "Use POST for this endpoint.",
            },
        )

    def do_POST(self):
        # Check that RENDER_TOKEN exists
        if not RENDER_TOKEN:
            self._send_json(
                500,
                {
                    "error": "RENDER_TOKEN is not configured"
                },
            )
            return

        # Check authentication
        token = self.headers.get("x-render-token")

        if token != RENDER_TOKEN:
            self._send_json(
                401,
                {
                    "error": "Unauthorized"
                },
            )
            return

        # Read request body
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)

            payload = json.loads(body.decode("utf-8"))

        except Exception:
            self._send_json(
                400,
                {
                    "error": "Invalid JSON"
                },
            )
            return

        # Accept either:
        #
        # {
        #     "quote": {...}
        # }
        #
        # or the quote object directly
        if isinstance(payload, dict) and "quote" in payload:
            quote = payload["quote"]
        else:
            quote = payload

        # Generate HTML
        try:
            html = render_html_from_quote(quote)

        except Exception as e:
            self._send_json(
                400,
                {
                    "error": "Render HTML failed",
                    "details": str(e),
                    "traceback":traceback.format_exc()
                },
            )
            return

        # Determine current Vercel host
        host = self.headers.get("host")

        if not host:
            self._send_json(
                500,
                {
                    "error": "Could not determine request host"
                },
            )
            return

        # Call the Node PDF renderer
        node_url = f"https://{host}/api/render-pdf"

        headers = {
            "Content-Type": "application/json",
            "x-render-token": RENDER_TOKEN,
        }

        try:
            response = requests.post(
                node_url,
                headers=headers,
                json={"html": html},
                timeout=60,
            )

        except Exception as e:
            self._send_json(
                500,
                {
                    "error": "Renderer request failed",
                    "details": str(e),
                },
            )
            return

        # Node renderer failed
        if response.status_code != 200:
            self._send_json(
                500,
                {
                    "error": "Renderer failed",
                    "status_code": response.status_code,
                    "details": response.text,
                },
            )
            return

        # Return PDF
        pdf_bytes = response.content

        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(pdf_bytes)))
        self.end_headers()

        self.wfile.write(pdf_bytes)
