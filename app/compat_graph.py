from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Tuple

START = "__start__"
END = "__end__"


@dataclass
class _CompiledGraph:
    nodes: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]
    edges: Dict[str, str]
    conditional_edges: Dict[str, Tuple[Callable[[Dict[str, Any]], str], Dict[str, str]]]

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
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
    nodes: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = field(default_factory=dict)
    edges: Dict[str, str] = field(default_factory=dict)
    conditional_edges: Dict[str, Tuple[Callable[[Dict[str, Any]], str], Dict[str, str]]] = field(default_factory=dict)

    def add_node(self, name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.nodes[name] = fn

    def add_edge(self, src: str, dst: str) -> None:
        self.edges[src] = dst

    def add_conditional_edges(
        self,
        src: str,
        router: Callable[[Dict[str, Any]], str],
        mapping: Dict[str, str],
    ) -> None:
        self.conditional_edges[src] = (router, mapping)

    def compile(self) -> _CompiledGraph:
        return _CompiledGraph(
            nodes=self.nodes,
            edges=self.edges,
            conditional_edges=self.conditional_edges,
        )
