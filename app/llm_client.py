from __future__ import annotations

import json
from typing import Any, Dict, List

import requests
from pydantic import ValidationError

from .config import SETTINGS
from .models import AnalysisResult
from .utils import extract_json_object, json_preview, now_iso, shorten


class LLMClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or SETTINGS.llm_base_url).rstrip("/")
        self.model = model or SETTINGS.llm_model
        self.timeout = SETTINGS.llm_timeout
        self.temperature = SETTINGS.llm_temperature
        self.max_tokens = SETTINGS.llm_max_tokens
        self.api_key = SETTINGS.llm_api_key
        self.trace_chars = SETTINGS.llm_trace_chars

    def healthcheck(self) -> Dict[str, Any]:
        info = {"base_url": self.base_url, "model": self.model, "reachable": False, "models": []}
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=10)
            info["status_code"] = resp.status_code
            if resp.ok:
                info["reachable"] = True
                payload = resp.json()
                models = payload.get("data", []) if isinstance(payload, dict) else []
                info["models"] = [m.get("id") for m in models if isinstance(m, dict)]
        except Exception as exc:
            info["error"] = str(exc)
        return info

    def analyze(self, incident_ts: str, evidence: Dict[str, Any], pass_name: str = "final") -> Dict[str, Any]:
        prompt = self._build_prompt(incident_ts=incident_ts, evidence=evidence, pass_name=pass_name)
        request_payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Linux SRE incident analyst. "
                        "Return ONLY one valid JSON object. "
                        "Do not include markdown or prose outside JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        try:
            response = self._chat(request_payload)
            content = response["content"]
            parsed = extract_json_object(content)
            if not parsed:
                return {
                    "analysis": self._fallback_analysis(f"Could not parse JSON from model output on {pass_name} pass."),
                    "trace": self._trace_payload(
                        pass_name=pass_name,
                        status="parse_error",
                        request_payload=request_payload,
                        response=response,
                        parsed_json=None,
                    ),
                }

            try:
                model = AnalysisResult.model_validate(parsed)
                analysis = model.model_dump()
                return {
                    "analysis": analysis,
                    "trace": self._trace_payload(
                        pass_name=pass_name,
                        status="ok",
                        request_payload=request_payload,
                        response=response,
                        parsed_json=analysis,
                    ),
                }
            except ValidationError as exc:
                return {
                    "analysis": self._fallback_analysis(f"Validation error from model output: {exc}"),
                    "trace": self._trace_payload(
                        pass_name=pass_name,
                        status="validation_error",
                        request_payload=request_payload,
                        response=response,
                        parsed_json=parsed,
                    ),
                }
        except Exception as exc:
            fallback = self._fallback_analysis(f"LLM call failed: {exc}")
            return {
                "analysis": fallback,
                "trace": {
                    "pass_name": pass_name,
                    "status": "request_error",
                    "created_at": now_iso(),
                    "request_payload": request_payload,
                    "request_preview": json_preview(request_payload, max_chars=5000),
                    "response_text": "",
                    "response_preview": "",
                    "response_json": {},
                    "parsed_json": fallback,
                    "usage": {},
                    "error": str(exc),
                },
            }

    def _chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("No choices returned by LLM server")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            text_parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            content = "\n".join(text_parts)
        return {
            "content": str(content),
            "json": data,
            "usage": data.get("usage", {}) if isinstance(data, dict) else {},
            "status_code": resp.status_code,
        }

    def _trace_payload(
        self,
        pass_name: str,
        status: str,
        request_payload: Dict[str, Any],
        response: Dict[str, Any],
        parsed_json: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        return {
            "pass_name": pass_name,
            "status": status,
            "created_at": now_iso(),
            "request_payload": request_payload,
            "request_preview": json_preview(request_payload, max_chars=5000),
            "response_text": response.get("content", ""),
            "response_preview": shorten(response.get("content", ""), self.trace_chars),
            "response_json": response.get("json", {}),
            "parsed_json": parsed_json or {},
            "usage": response.get("usage", {}),
            "status_code": response.get("status_code"),
        }

    def _build_prompt(self, incident_ts: str, evidence: Dict[str, Any], pass_name: str) -> str:
        schema = {
            "summary": "string",
            "overall_confidence": 0.0,
            "analysis_notes": ["brief observable analyst log entries"],
            "evidence_map": [
                {
                    "signal": "string",
                    "effect": "supports|refutes|context|unknown",
                    "detail": "string",
                }
            ],
            "top_hypotheses": [
                {
                    "title": "string",
                    "category": "memory|kernel|disk|thermal|gpu|power|network|unknown",
                    "confidence": 0.0,
                    "likely_root_cause": "string",
                    "evidence": ["string"],
                    "next_checks": ["string"],
                    "remediation": ["string"],
                }
            ],
            "missing_evidence": ["string"],
            "recommended_priority": "low|medium|high|critical",
        }
        return (
            f"Incident timestamp: {incident_ts}\n"
            f"Pass: {pass_name}\n"
            "Task: Analyze a Linux freeze/hang using only the supplied evidence. "
            "Prioritize hard evidence over guesses. Use at most 3 hypotheses. "
            "If evidence is weak, lower confidence and ask for more evidence.\n\n"
            "Important constraint: 'analysis_notes' must be a concise observable audit log, "
            "not hidden chain-of-thought. Keep them short and factual.\n\n"
            f"Output schema exactly as JSON:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
            f"Evidence JSON:\n{json.dumps(evidence, ensure_ascii=False)}"
        )

    def _fallback_analysis(self, reason: str) -> Dict[str, Any]:
        return {
            "summary": "LLM analysis unavailable. Review rule-based findings and collected artifacts.",
            "overall_confidence": 0.15,
            "analysis_notes": [
                "LLM response was unavailable or invalid.",
                "Fallback report generated from rules and collected artifacts.",
            ],
            "evidence_map": [
                {
                    "signal": "llm_unavailable",
                    "effect": "context",
                    "detail": reason,
                }
            ],
            "top_hypotheses": [
                {
                    "title": "LLM unavailable",
                    "category": "unknown",
                    "confidence": 0.15,
                    "likely_root_cause": reason,
                    "evidence": [reason],
                    "next_checks": [
                        "Verify llama-server is running",
                        "Check /v1/models and /v1/chat/completions reachability",
                        "Retry with a smaller or instruction-tuned model",
                    ],
                    "remediation": [
                        "Use --skip-llm for rule-only reports if the model server is down",
                    ],
                }
            ],
            "missing_evidence": [reason],
            "recommended_priority": "medium",
        }
