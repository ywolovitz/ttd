# api/index.py
import os
import json
from http import HTTPStatus
from flask import Request  # Vercel Python runtime exposes a Flask-like request
import requests

# Import your HTML generation function (create render_lib.py as shown below)
from render_lib import render_html_from_quote

RENDER_TOKEN = os.environ.get("RENDER_TOKEN")

def handler(request: Request):
    # Only accept POST
    if request.method != "POST":
        return ("Method Not Allowed", HTTPStatus.METHOD_NOT_ALLOWED, {"Content-Type": "application/json"})

    # Simple header auth
    token = request.headers.get("x-render-token")
    if token != RENDER_TOKEN:
        return (json.dumps({"error":"Unauthorized"}), HTTPStatus.UNAUTHORIZED, {"Content-Type":"application/json"})

    # Parse JSON body
    try:
        payload = request.get_json(force=True)
    except Exception:
        return (json.dumps({"error":"Invalid JSON"}), HTTPStatus.BAD_REQUEST, {"Content-Type":"application/json"})

    # Accept either { "quote": {...} } or the quote object directly
    quote = payload.get("quote") if isinstance(payload, dict) and "quote" in payload else payload

    # Render HTML using your Python logic
    try:
        html = render_html_from_quote(quote)
    except Exception as e:
        return (json.dumps({"error":"Render HTML failed", "details": str(e)}), HTTPStatus.BAD_REQUEST, {"Content-Type":"application/json"})

    # Forward HTML to internal Node renderer
    host = request.headers.get("host")
    node_url = f"https://{host}/api/render-pdf."
    headers = {"Content-Type":"application/json", "x-render-token": RENDER_TOKEN}

    try:
        resp = requests.post(node_url, headers=headers, json={"html": html}, timeout=60)
    except Exception as e:
        return (json.dumps({"error":"Renderer request failed", "details": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR, {"Content-Type":"application/json"})

    if resp.status_code != 200:
        return (json.dumps({"error":"Renderer failed", "details": resp.text}), HTTPStatus.INTERNAL_SERVER_ERROR, {"Content-Type":"application/json"})

    pdf_bytes = resp.content
    return (pdf_bytes, HTTPStatus.OK, {"Content-Type":"application/pdf", "Content-Length": str(len(pdf_bytes))})
