from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="10-K DCF")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>10-K DCF</title>
    <style>
      body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 4rem auto; padding: 0 1rem; }
      code { background: #eee; padding: 0.1rem 0.3rem; border-radius: 4px; }
    </style>
  </head>
  <body>
    <h1>10-K DCF</h1>
    <p>Hello, world. The app is running.</p>
    <p>API docs: <a href="/docs"><code>/docs</code></a></p>
  </body>
</html>
"""


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
