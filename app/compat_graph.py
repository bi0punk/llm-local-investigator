from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

START = "__start__"
END = "__end__"


@dataclass
class _CompiledGraph:
    nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]
    edges: dict[str, str]
    conditional_edges: dict[str, tuple[Callable[[dict[str, Any]], str], dict[str, str]]]

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        current = self.edges.get(START)
        if not current:
            raise RuntimeError("Graph has no START edge")
        working = dict(state)

        while current != END:
            node_fn = self.nodes[current]
            update = node_fn(working) or {}
            if not isinstance(update, dict):
                raise RuntimeError(f"Node {current} did not return a dict")
            working.update(update)

            if current in self.conditional_edges:
                router, mapping = self.conditional_edges[current]
                route_key = router(working)
                if route_key not in mapping:
                    raise RuntimeError(f"Conditional route {route_key!r} not in mapping for node {current}")
                current = mapping[route_key]
            else:
                current = self.edges.get(current, END)

        return working


@dataclass
class StateGraph:
    state_type: Any
    nodes: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = field(default_factory=dict)
    edges: dict[str, str] = field(default_factory=dict)
    conditional_edges: dict[str, tuple[Callable[[dict[str, Any]], str], dict[str, str]]] = field(default_factory=dict)

    def add_node(self, name: str, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.nodes[name] = fn

    def add_edge(self, src: str, dst: str) -> None:
        self.edges[src] = dst

    def add_conditional_edges(
        self,
        src: str,
        router: Callable[[dict[str, Any]], str],
        mapping: dict[str, str],
    ) -> None:
        self.conditional_edges[src] = (router, mapping)

    def compile(self) -> _CompiledGraph:
        return _CompiledGraph(
            nodes=self.nodes,
            edges=self.edges,
            conditional_edges=self.conditional_edges,
        )
