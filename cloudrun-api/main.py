from flask import Flask, request, Response
import requests

app = Flask(__name__)

# Your existing GKE Load Balancer / nip.io URL
BACKEND_URL = "https://136.110.180.171.nip.io"

@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy(path):
    url = f"{BACKEND_URL}/{path}"
    resp = requests.request(
        method=request.method,
        url=url,
        headers={k: v for k, v in request.headers if k.lower() != "host"},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
    )
    return Response(resp.content, resp.status_code, resp.headers.items())

@app.route("/health")
def health():
    return "OK", 200
