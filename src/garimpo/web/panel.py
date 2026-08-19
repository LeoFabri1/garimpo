"""Local read-only web panel (stdlib only, localhost default)."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from garimpo.mcp import queries


def serve(db_path: str | Path, *, host: str = "127.0.0.1", port: int = 8765) -> None:
    db = str(db_path)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/history":
                qs = parse_qs(parsed.query)
                model = (qs.get("model") or ["rtx_5070_ti"])[0]
                data = queries.query_price_history(db, model, days=90)
                self._json(data)
                return
            if parsed.path == "/api/models":
                from garimpo.catalog import load_gpu_catalog

                cats = load_gpu_catalog()
                self._json({"models": sorted(cats.products.keys())})
                return
            if parsed.path in {"/", "/index.html"}:
                self._html(_PAGE)
                return
            self.send_error(404)

        def _json(self, data: object) -> None:
            body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer((host, port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


_PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Garimpo — histórico</title>
  <style>
    :root { color-scheme: light; --bg:#f6f4ef; --ink:#1a1a1a; --muted:#666; --line:#ccc; }
    body { margin:0; font-family: "IBM Plex Sans", system-ui, sans-serif; background:var(--bg); color:var(--ink); }
    main { max-width: 920px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
    h1 { font-weight: 600; letter-spacing: -0.02em; margin: 0 0 .25rem; }
    p.sub { color: var(--muted); margin: 0 0 1.5rem; }
    label { display:block; font-size:.85rem; color:var(--muted); margin-bottom:.35rem; }
    select { font: inherit; padding:.5rem .75rem; border:1px solid var(--line); background:#fff; min-width: 16rem; }
    .stats { display:flex; gap:1.5rem; flex-wrap:wrap; margin:1.25rem 0; }
    .stats div { min-width: 6rem; }
    .stats strong { display:block; font-size:1.25rem; }
    .stats span { color:var(--muted); font-size:.8rem; }
    svg { width:100%; height:280px; background:#fff; border:1px solid var(--line); }
    .warn { margin-top:2rem; font-size:.8rem; color:var(--muted); }
  </style>
</head>
<body>
<main>
  <h1>Garimpo</h1>
  <p class="sub">Histórico local de preços (somente leitura)</p>
  <label for="model">Modelo</label>
  <select id="model"></select>
  <div class="stats">
    <div><strong id="n">—</strong><span>amostras</span></div>
    <div><strong id="min">—</strong><span>mín 90d</span></div>
    <div><strong id="med">—</strong><span>mediana</span></div>
    <div><strong id="max">—</strong><span>máx 90d</span></div>
  </div>
  <svg id="chart" viewBox="0 0 900 280" preserveAspectRatio="none"></svg>
  <p class="warn">Bind padrão: localhost. Não exponha na internet sem autenticação.</p>
</main>
<script>
async function loadModels() {
  const r = await fetch('/api/models');
  const data = await r.json();
  const sel = document.getElementById('model');
  sel.innerHTML = data.models.map(m => `<option value="${m}">${m}</option>`).join('');
  sel.onchange = () => loadHistory(sel.value);
  if (data.models.length) loadHistory(data.models[0]);
}
function brl(v) {
  if (v == null) return '—';
  return 'R$ ' + Number(v).toLocaleString('pt-BR', {maximumFractionDigits: 0});
}
async function loadHistory(model) {
  const r = await fetch('/api/history?model=' + encodeURIComponent(model));
  const data = await r.json();
  document.getElementById('n').textContent = data.n || 0;
  document.getElementById('min').textContent = brl(data.min);
  document.getElementById('med').textContent = brl(data.median);
  document.getElementById('max').textContent = brl(data.max);
  draw(data.series || []);
}
function draw(series) {
  const svg = document.getElementById('chart');
  svg.innerHTML = '';
  if (series.length < 2) {
    svg.innerHTML = '<text x="20" y="140" fill="#666">Poucos pontos para gráfico</text>';
    return;
  }
  const prices = series.map(p => p.price);
  const min = Math.min(...prices), max = Math.max(...prices);
  const pad = 20, w = 900, h = 280;
  const pts = series.map((p, i) => {
    const x = pad + (i / (series.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((p.price - min) / (max - min || 1)) * (h - 2 * pad);
    return `${x},${y}`;
  }).join(' ');
  const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
  poly.setAttribute('fill', 'none');
  poly.setAttribute('stroke', '#1a1a1a');
  poly.setAttribute('stroke-width', '2');
  poly.setAttribute('points', pts);
  svg.appendChild(poly);
}
loadModels();
</script>
</body>
</html>
"""
