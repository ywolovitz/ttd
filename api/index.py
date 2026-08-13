import os
import json

from flask import Flask, request
import requests

from render_lib import render_html_from_quote


app = Flask(__name__)

RENDER_TOKEN = os.environ.get("RENDER_TOKEN")


@app.route("/", methods=["POST"])
def handler():
    # Check that the render token is configured
    if not RENDER_TOKEN:
        return (
            json.dumps({"error": "RENDER_TOKEN is not configured"}),
            500,
            {"Content-Type": "application/json"},
        )

    # Check authentication
    token = request.headers.get("x-render-token")

    if token != RENDER_TOKEN:
        return (
            json.dumps({"error": "Unauthorized"}),
            401,
            {"Content-Type": "application/json"},
        )

    # Parse JSON body
    try:
        payload = request.get_json(force=True)
    except Exception:
        return (
            json.dumps({"error": "Invalid JSON"}),
            400,
            {"Content-Type": "application/json"},
        )

    # Accept either:
    # { "quote": {...} }
    # or the quote object directly
    if isinstance(payload, dict) and "quote" in payload:
        quote = payload["quote"]
    else:
        quote = payload

    # Generate HTML
    try:
        html = render_html_from_quote(quote)
    except Exception as e:
        return (
            json.dumps({
                "error": "Render HTML failed",
                "details": str(e),
            }),
            400,
            {"Content-Type": "application/json"},
        )

    # Call the Node PDF renderer
    host = request.headers.get("host")

    if not host:
        return (
            json.dumps({"error": "Could not determine request host"}),
            500,
            {"Content-Type": "application/json"},
        )

    node_url = f"https://{host}/api/render-pdf"

    headers = {
        "Content-Type": "application/json",
        "x-render-token": RENDER_TOKEN,
    }

    try:
        resp = requests.post(
            node_url,
            headers=headers,
            json={"html": html},
            timeout=60,
        )
    except Exception as e:
        return (
            json.dumps({
                "error": "Renderer request failed",
                "details": str(e),
            }),
            500,
            {"Content-Type": "application/json"},
        )

    # Node renderer failed
    if resp.status_code != 200:
        return (
            json.dumps({
                "error": "Renderer failed",
                "status_code": resp.status_code,
                "details": resp.text,
            }),
            500,
            {"Content-Type": "application/json"},
        )

    # Return the generated PDF
    pdf_bytes = resp.content

    return (
        pdf_bytes,
        200,
        {
            "Content-Type": "application/pdf",
            "Content-Length": str(len(pdf_bytes)),
        },
    )
