from fastapi import FastAPI, Request, Response
import httpx
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import CollectorRegistry, multiprocess
import time
import os
import json

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
PORT = int(os.environ.get("PROXY_PORT", "9200"))

app = FastAPI()

REQUEST_DURATION = Histogram(
    "ollama_request_duration_seconds",
    "Request duration to Ollama through proxy",
    ['method', 'endpoint', 'model']
)
REQUEST_COUNTER = Counter(
    "ollama_request_total",
    "Number of requests proxied to Ollama",
    ['method', 'endpoint', 'model', 'status']
)
REQUEST_ERRORS = Counter(
    "ollama_request_errors_total",
    "Number of errored requests proxied to Ollama",
    ['method', 'endpoint', 'model', 'error_type']
)
TOKENS_IN = Counter(
    "ollama_tokens_in_total",
    "Total input tokens observed",
    ['model']
)
TOKENS_OUT = Counter(
    "ollama_tokens_out_total",
    "Total output tokens observed",
    ['model']
)

client = httpx.AsyncClient(timeout=60.0)


async def extract_model_and_tokens(req: Request, resp: Response, body: bytes):
    model = "unknown"
    # Try to parse body for model
    try:
        data = json.loads(body.decode('utf-8')) if body else {}
        if isinstance(data, dict):
            model = data.get('model', model)
    except Exception:
        pass

    # Attempt to extract token usage from response JSON (if Ollama returns it)
    try:
        data = await resp.aread()
        text = data.decode('utf-8')
        j = json.loads(text)
        # Common pattern: j.get('usage', {}).get('total_tokens') or j['usage']['prompt_tokens'] etc.
        usage = j.get('usage') if isinstance(j, dict) else None
        if usage and isinstance(usage, dict):
            in_tokens = usage.get('prompt_tokens') or usage.get('input_tokens') or usage.get('input_tokens_total')
            out_tokens = usage.get('completion_tokens') or usage.get('output_tokens') or usage.get('output_tokens_total')
            if in_tokens:
                TOKENS_IN.labels(model=model).inc(float(in_tokens))
            if out_tokens:
                TOKENS_OUT.labels(model=model).inc(float(out_tokens))
    except Exception:
        # ignore token parsing errors
        pass


@app.middleware("http")
async def proxy_middleware(request: Request, call_next):
    start = time.time()
    path = request.url.path
    method = request.method
    body = await request.body()

    # Forward to upstream Ollama
    upstream_url = f"{OLLAMA_URL}{path}"
    model = "unknown"
    try:
        # Try to get model from body
        if body:
            try:
                data = json.loads(body.decode('utf-8'))
                if isinstance(data, dict):
                    model = data.get('model', model)
            except Exception:
                pass

        resp = await client.request(method, upstream_url, content=body, headers=dict(request.headers))
        duration = time.time() - start
        REQUEST_DURATION.labels(method=method, endpoint=path, model=model).observe(duration)
        status = str(resp.status_code)
        REQUEST_COUNTER.labels(method=method, endpoint=path, model=model, status=status).inc()

        # Try to parse token usage from response
        try:
            j = resp.json()
            usage = None
            if isinstance(j, dict):
                usage = j.get('usage')
            if usage and isinstance(usage, dict):
                in_tokens = usage.get('prompt_tokens') or usage.get('input_tokens')
                out_tokens = usage.get('completion_tokens') or usage.get('output_tokens')
                if in_tokens:
                    TOKENS_IN.labels(model=model).inc(float(in_tokens))
                if out_tokens:
                    TOKENS_OUT.labels(model=model).inc(float(out_tokens))
        except Exception:
            pass

        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))
    except Exception as e:
        duration = time.time() - start
        REQUEST_DURATION.labels(method=method, endpoint=path, model=model).observe(duration)
        REQUEST_ERRORS.labels(method=method, endpoint=path, model=model, error_type=type(e).__name__).inc()
        REQUEST_COUNTER.labels(method=method, endpoint=path, model=model, status="error").inc()
        return Response(content=str(e), status_code=502)


@app.get("/metrics")
async def metrics():
    # Return the prometheus metrics
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=PORT)
