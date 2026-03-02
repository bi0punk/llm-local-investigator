from __future__ import annotations

from flask import Flask, abort, jsonify, render_template_string

from .storage import Storage

INDEX_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Freeze Investigator Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0f172a; color: #e5e7eb; margin: 0; }
    .wrap { max-width: 1280px; margin: 0 auto; padding: 1.2rem; }
    .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 14px; padding: 1rem; margin-bottom: 1rem; }
    a { color: #7dd3fc; text-decoration: none; }
    table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
    th, td { padding: .65rem; border-bottom: 1px solid #1f2937; text-align: left; vertical-align: top; }
    .badge { display:inline-block; padding:.15rem .45rem; border-radius:999px; border:1px solid #334155; background:#020617; }
    code, pre { background: #020617; color: #cbd5e1; border-radius: 8px; }
    pre { padding: .8rem; overflow-x: auto; white-space: pre-wrap; }
    .muted { color: #94a3b8; }
  </style>
</head>
<body>
<div class="wrap">
  <h1>Freeze Investigator Dashboard</h1>
  <p class="muted">Incidentes recientes, trazas de análisis y snapshots preventivos.</p>
  <div class="grid">
    <div>
      <div class="card">
        <h2>Incidentes</h2>
        <table>
          <thead>
            <tr>
              <th>Fecha incidente</th>
              <th>Prioridad</th>
              <th>Score / categoría</th>
              <th>Resumen</th>
              <th>Detalle</th>
            </tr>
          </thead>
          <tbody>
          {% for item in incidents %}
            <tr>
              <td>{{ item.incident_ts }}</td>
              <td><span class="badge">{{ item.recommended_priority }}</span></td>
              <td>{{ item.top_category }} / {{ "%.2f"|format(item.overall_confidence or 0) }}</td>
              <td>{{ item.summary }}</td>
              <td><a href="/incident/{{ item.id }}">abrir</a></td>
            </tr>
          {% endfor %}
          {% if not incidents %}
            <tr><td colspan="5">No hay incidentes indexados todavía.</td></tr>
          {% endif %}
          </tbody>
        </table>
      </div>
    </div>
    <div>
      <div class="card">
        <h2>Snapshots recientes</h2>
        <table>
          <thead><tr><th>captured_at</th><th>archivo</th></tr></thead>
          <tbody>
          {% for item in snapshots %}
            <tr>
              <td>{{ item.captured_at }}</td>
              <td>{{ item.source_file }}</td>
            </tr>
          {% endfor %}
          {% if not snapshots %}
            <tr><td colspan="2">No hay snapshots</td></tr>
          {% endif %}
          </tbody>
        </table>
      </div>
      <div class="card">
        <h2>APIs</h2>
        <ul>
          <li><a href="/api/incidents">/api/incidents</a></li>
          <li><a href="/api/snapshots">/api/snapshots</a></li>
        </ul>
      </div>
    </div>
  </div>
</div>
</body>
</html>
"""

DETAIL_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Incident {{ incident.id }}</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0f172a; color: #e5e7eb; margin: 0; }
    .wrap { max-width: 1280px; margin: 0 auto; padding: 1.2rem; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 14px; padding: 1rem; margin-bottom: 1rem; }
    a { color: #7dd3fc; text-decoration: none; }
    table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
    th, td { padding: .65rem; border-bottom: 1px solid #1f2937; text-align: left; vertical-align: top; }
    .badge { display:inline-block; padding:.15rem .45rem; border-radius:999px; border:1px solid #334155; background:#020617; }
    code, pre { background: #020617; color: #cbd5e1; border-radius: 8px; }
    pre { padding: .8rem; overflow-x: auto; white-space: pre-wrap; }
    details { margin-bottom: .75rem; }
    iframe { width: 100%; min-height: 960px; border: 1px solid #334155; border-radius: 12px; background: #fff; }
  </style>
</head>
<body>
<div class="wrap">
  <p><a href="/">← volver</a></p>
  <h1>Incidente {{ incident.incident_ts }}</h1>

  <div class="card">
    <p><strong>Prioridad:</strong> <span class="badge">{{ incident.recommended_priority }}</span></p>
    <p><strong>Confianza global:</strong> {{ incident.final_analysis.get("overall_confidence", "n/a") }}</p>
    <p><strong>Top categoría:</strong> {{ incident.top_category }}</p>
    <p><strong>Señal más fuerte:</strong> {{ incident.strongest_signal }}</p>
    <p><strong>Resumen:</strong> {{ incident.summary }}</p>
  </div>

  <div class="card">
    <h2>Notas de análisis</h2>
    <ul>
      {% for item in incident.final_analysis.get("analysis_notes", []) %}
        <li>{{ item }}</li>
      {% endfor %}
      {% if not incident.final_analysis.get("analysis_notes", []) %}
        <li>Sin notas</li>
      {% endif %}
    </ul>
  </div>

  <div class="card">
    <h2>Hipótesis</h2>
    {% for hyp in incident.final_analysis.get("top_hypotheses", []) %}
      <div style="margin-bottom: 1rem;">
        <h3>{{ loop.index }}. {{ hyp.title }} <span class="badge">{{ hyp.category }} / {{ hyp.confidence }}</span></h3>
        <p><strong>Causa probable:</strong> {{ hyp.likely_root_cause }}</p>
        <p><strong>Evidencia:</strong></p>
        <ul>{% for item in hyp.evidence %}<li>{{ item }}</li>{% endfor %}</ul>
        <p><strong>Siguientes checks:</strong></p>
        <ul>{% for item in hyp.next_checks %}<li>{{ item }}</li>{% endfor %}</ul>
      </div>
    {% endfor %}
    {% if not incident.final_analysis.get("top_hypotheses", []) %}
      <p>Sin hipótesis</p>
    {% endif %}
  </div>

  <div class="card">
    <h2>Trazas por nodo</h2>
    <table>
      <thead><tr><th>Nodo</th><th>Estado</th><th>Inicio</th><th>Fin</th><th>ms</th><th>Nota</th></tr></thead>
      <tbody>
      {% for item in incident.traces %}
        <tr>
          <td>{{ item.node_name }}</td>
          <td>{{ item.status }}</td>
          <td>{{ item.started_at }}</td>
          <td>{{ item.finished_at }}</td>
          <td>{{ item.duration_ms }}</td>
          <td>{{ item.note }}</td>
        </tr>
      {% endfor %}
      {% if not incident.traces %}
        <tr><td colspan="6">Sin trazas</td></tr>
      {% endif %}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>LLM</h2>
    {% for item in incident.llm_calls %}
      <details open>
        <summary>{{ item.pass_name }} / {{ item.status }}</summary>
        <p><strong>Usage:</strong> {{ item.usage }}</p>
        <p><strong>Request file:</strong> {{ item.request_path }}</p>
        <p><strong>Parsed file:</strong> {{ item.parsed_path }}</p>
        <p><strong>Raw response file:</strong> {{ item.raw_response_path }}</p>
        <details>
          <summary>Request preview</summary>
          <pre>{{ item.request_preview }}</pre>
        </details>
        <details>
          <summary>Response preview</summary>
          <pre>{{ item.response_preview }}</pre>
        </details>
        <details>
          <summary>Parsed JSON</summary>
          <pre>{{ item.parsed_json }}</pre>
        </details>
      </details>
    {% endfor %}
    {% if not incident.llm_calls %}
      <p>Sin llamadas LLM registradas</p>
    {% endif %}
  </div>

  <div class="card">
    <h2>Reporte HTML generado</h2>
    {% if incident.report_html %}
      <iframe srcdoc="{{ incident.report_html|e }}"></iframe>
    {% else %}
      <p>No hay reporte HTML disponible.</p>
    {% endif %}
  </div>
</div>
</body>
</html>
"""


def create_app() -> Flask:
    app = Flask(__name__)
    storage = Storage()

    @app.get("/")
    def index():
        incidents = storage.list_incidents(limit=100)
        snapshots = storage.list_snapshots(limit=30)
        return render_template_string(INDEX_TEMPLATE, incidents=incidents, snapshots=snapshots)

    @app.get("/incident/<int:incident_id>")
    def incident_detail(incident_id: int):
        incident = storage.get_incident(incident_id)
        if not incident:
            abort(404)
        return render_template_string(DETAIL_TEMPLATE, incident=incident)

    @app.get("/api/incidents")
    def api_incidents():
        return jsonify(storage.list_incidents(limit=500))

    @app.get("/api/incidents/<int:incident_id>")
    def api_incident_detail(incident_id: int):
        incident = storage.get_incident(incident_id)
        if not incident:
            abort(404)
        return jsonify(incident)

    @app.get("/api/snapshots")
    def api_snapshots():
        return jsonify(storage.list_snapshots(limit=500))

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    return app
