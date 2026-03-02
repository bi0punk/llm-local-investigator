from __future__ import annotations

from typing import Any, Dict, List

from jinja2 import Template

HTML_TEMPLATE = Template(
    """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Freeze Investigator Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; color: #e5e7eb; background: #0f172a; }
    h1, h2, h3 { color: #f8fafc; }
    .muted { color: #94a3b8; }
    .card { border: 1px solid #334155; border-radius: 14px; padding: 1rem 1.2rem; margin-bottom: 1rem; background: #111827; }
    .badge { display: inline-block; padding: .2rem .55rem; border-radius: 999px; background: #1e293b; border: 1px solid #334155; }
    code, pre { background: #020617; color: #cbd5e1; }
    pre { padding: .8rem; border-radius: 10px; overflow-x: auto; white-space: pre-wrap; }
    ul { line-height: 1.5; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: .55rem; border-bottom: 1px solid #1f2937; vertical-align: top; }
  </style>
</head>
<body>
  <h1>Reporte incidente {{ incident_ts }}</h1>
  <p class="muted">Ventana analizada: {{ since }} -> {{ until }}</p>

  <div class="card">
    <h2>Resumen</h2>
    <p>{{ summary }}</p>
    <p><strong>Confianza global:</strong> {{ overall_confidence }} | <strong>Prioridad:</strong> {{ recommended_priority }}</p>
  </div>

  <div class="card">
    <h2>Ranking por reglas</h2>
    <table>
      <thead><tr><th>Categoría</th><th>Score</th></tr></thead>
      <tbody>
      {% for item in ranked_categories %}
        <tr><td>{{ item[0] }}</td><td>{{ item[1] }}</td></tr>
      {% endfor %}
      {% if not ranked_categories %}
        <tr><td colspan="2">Sin categorías destacadas</td></tr>
      {% endif %}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Notas de análisis</h2>
    <ul>
    {% for item in analysis_notes %}
      <li>{{ item }}</li>
    {% endfor %}
    {% if not analysis_notes %}
      <li>Sin notas declaradas</li>
    {% endif %}
    </ul>
  </div>

  <div class="card">
    <h2>Mapa de evidencia</h2>
    <table>
      <thead><tr><th>Señal</th><th>Efecto</th><th>Detalle</th></tr></thead>
      <tbody>
      {% for item in evidence_map %}
        <tr><td>{{ item.signal }}</td><td>{{ item.effect }}</td><td>{{ item.detail }}</td></tr>
      {% endfor %}
      {% if not evidence_map %}
        <tr><td colspan="3">Sin mapa de evidencia</td></tr>
      {% endif %}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Hipótesis</h2>
    {% for hyp in top_hypotheses %}
      <div style="margin-bottom: 1rem;">
        <h3>{{ loop.index }}. {{ hyp.title }} <span class="badge">{{ hyp.category }} | {{ hyp.confidence }}</span></h3>
        <p><strong>Causa probable:</strong> {{ hyp.likely_root_cause }}</p>
        <p><strong>Evidencia:</strong></p>
        <ul>{% for item in hyp.evidence %}<li>{{ item }}</li>{% endfor %}</ul>
        <p><strong>Siguientes checks:</strong></p>
        <ul>{% for item in hyp.next_checks %}<li>{{ item }}</li>{% endfor %}</ul>
        <p><strong>Remediación:</strong></p>
        <ul>{% for item in hyp.remediation %}<li>{{ item }}</li>{% endfor %}</ul>
      </div>
    {% endfor %}
    {% if not top_hypotheses %}
      <p>Sin hipótesis generadas</p>
    {% endif %}
  </div>

  <div class="card">
    <h2>Evidencia faltante</h2>
    <ul>{% for item in missing_evidence %}<li>{{ item }}</li>{% endfor %}</ul>
    {% if not missing_evidence %}<p>Ninguna declarada</p>{% endif %}
  </div>

  <div class="card">
    <h2>Señales detectadas</h2>
    {% for name, values in signals.items() %}
      <h3>{{ name }}</h3>
      <ul>{% for line in values %}<li><code>{{ line }}</code></li>{% endfor %}</ul>
    {% endfor %}
    {% if not signals %}<p>No se detectaron señales fuertes por reglas.</p>{% endif %}
  </div>

  <div class="card">
    <h2>Trazas por nodo</h2>
    <table>
      <thead><tr><th>Nodo</th><th>Estado</th><th>Duración ms</th><th>Nota</th></tr></thead>
      <tbody>
      {% for item in trace_events %}
        <tr><td>{{ item.node_name }}</td><td>{{ item.status }}</td><td>{{ item.duration_ms }}</td><td>{{ item.note }}</td></tr>
      {% endfor %}
      {% if not trace_events %}
        <tr><td colspan="4">Sin trazas</td></tr>
      {% endif %}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Trazas LLM</h2>
    {% for item in llm_calls %}
      <div style="margin-bottom: 1rem;">
        <h3>{{ item.pass_name }} <span class="badge">{{ item.status }}</span></h3>
        <p><strong>Usage:</strong> {{ item.usage }}</p>
        <details>
          <summary>Request preview</summary>
          <pre>{{ item.request_preview }}</pre>
        </details>
        <details>
          <summary>Response preview</summary>
          <pre>{{ item.response_preview }}</pre>
        </details>
      </div>
    {% endfor %}
    {% if not llm_calls %}
      <p>Sin llamadas LLM registradas</p>
    {% endif %}
  </div>
</body>
</html>
"""
)


def render_markdown(state: Dict[str, Any]) -> str:
    analysis = state.get("final_analysis") or state.get("preliminary_analysis") or {}
    rule_summary = state.get("rule_summary", {})
    lines: List[str] = []
    lines.append(f"# Reporte incidente {state['incident_ts']}")
    lines.append("")
    lines.append(f"**Ventana analizada:** {state['since']} -> {state['until']}")
    lines.append("")
    lines.append("## Resumen")
    lines.append(analysis.get("summary", "No summary available"))
    lines.append("")
    lines.append(f"- Confianza global: {analysis.get('overall_confidence', 'n/a')}")
    lines.append(f"- Prioridad recomendada: {analysis.get('recommended_priority', 'n/a')}")
    lines.append("")
    lines.append("## Ranking por reglas")
    for category, score in rule_summary.get("ranked_categories", []):
        lines.append(f"- {category}: {score}")
    if not rule_summary.get("ranked_categories"):
        lines.append("- Sin categorías destacadas")
    lines.append("")
    lines.append("## Notas de análisis")
    for item in analysis.get("analysis_notes", []):
        lines.append(f"- {item}")
    if not analysis.get("analysis_notes"):
        lines.append("- Sin notas de análisis")
    lines.append("")
    lines.append("## Mapa de evidencia")
    for item in analysis.get("evidence_map", []):
        lines.append(f"- {item['signal']} [{item['effect']}]: {item['detail']}")
    if not analysis.get("evidence_map"):
        lines.append("- Sin mapa de evidencia")
    lines.append("")
    lines.append("## Hipótesis")
    for idx, hyp in enumerate(analysis.get("top_hypotheses", []), 1):
        lines.append(f"### {idx}. {hyp['title']} [{hyp['category']}] ({hyp['confidence']})")
        lines.append(f"- Causa probable: {hyp['likely_root_cause']}")
        lines.append("- Evidencia:")
        for item in hyp.get("evidence", []):
            lines.append(f"  - {item}")
        lines.append("- Siguientes checks:")
        for item in hyp.get("next_checks", []):
            lines.append(f"  - {item}")
        lines.append("- Remediación:")
        for item in hyp.get("remediation", []):
            lines.append(f"  - {item}")
        lines.append("")
    if not analysis.get("top_hypotheses"):
        lines.append("- Sin hipótesis generadas")
        lines.append("")
    lines.append("## Evidencia faltante")
    for item in analysis.get("missing_evidence", []):
        lines.append(f"- {item}")
    if not analysis.get("missing_evidence"):
        lines.append("- Ninguna declarada")
    lines.append("")
    lines.append("## Señales detectadas")
    for name, values in (state.get("signals") or {}).items():
        lines.append(f"### {name}")
        for line in values:
            lines.append(f"- `{line}`")
        lines.append("")
    if not state.get("signals"):
        lines.append("- No se detectaron señales fuertes por reglas.")
    lines.append("")
    lines.append("## Decisión de probes extra")
    decision = state.get("decision", {})
    lines.append(f"- Ejecutar probes extra: {decision.get('run_extra_probes', False)}")
    lines.append(f"- Perfiles: {', '.join(decision.get('profiles', [])) or 'ninguno'}")
    lines.append(f"- Motivo: {decision.get('reason', 'n/a')}")
    lines.append("")
    lines.append("## Trazas por nodo")
    for item in state.get("trace_events", []):
        lines.append(f"- {item['node_name']} | {item['status']} | {item['duration_ms']} ms | {item['note']}")
    if not state.get("trace_events"):
        lines.append("- Sin trazas")
    lines.append("")
    lines.append("## Trazas LLM")
    for item in state.get("llm_calls", []):
        lines.append(f"### {item.get('pass_name')} [{item.get('status')}]")
        lines.append(f"- Usage: {item.get('usage', {})}")
        lines.append("- Request preview:")
        lines.append("```")
        lines.append(item.get("request_preview", ""))
        lines.append("```")
        lines.append("- Response preview:")
        lines.append("```")
        lines.append(item.get("response_preview", ""))
        lines.append("```")
        lines.append("")
    if not state.get("llm_calls"):
        lines.append("- Sin llamadas LLM registradas")
    return "\n".join(lines)


def render_html(state: Dict[str, Any]) -> str:
    analysis = state.get("final_analysis") or state.get("preliminary_analysis") or {}
    rule_summary = state.get("rule_summary", {})
    return HTML_TEMPLATE.render(
        incident_ts=state.get("incident_ts"),
        since=state.get("since"),
        until=state.get("until"),
        summary=analysis.get("summary", "No summary available"),
        overall_confidence=analysis.get("overall_confidence", "n/a"),
        recommended_priority=analysis.get("recommended_priority", "n/a"),
        analysis_notes=analysis.get("analysis_notes", []),
        evidence_map=analysis.get("evidence_map", []),
        top_hypotheses=analysis.get("top_hypotheses", []),
        missing_evidence=analysis.get("missing_evidence", []),
        ranked_categories=rule_summary.get("ranked_categories", []),
        signals=state.get("signals", {}),
        trace_events=state.get("trace_events", []),
        llm_calls=state.get("llm_calls", []),
    )
