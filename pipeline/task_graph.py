"""
task_graph.py - DAG planning and execution order for SmartRoute.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TaskNode:
    id: str
    task: str
    role: str = "coder"
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class TaskEdge:
    from_node: str
    to_node: str


class TaskGraphEngine:
    """
    Maintain execution DAG, supports topological order scheduling.
    """

    def __init__(self, nodes: Optional[List[TaskNode]] = None, edges: Optional[List[TaskEdge]] = None):
        self.nodes = nodes or []
        self.edges = edges or []
        self._node_map = {n.id: n for n in self.nodes}

    @classmethod
    def from_json_file(cls, path: str) -> "TaskGraphEngine":
        p = Path(path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        nodes = []
        for item in data.get("nodes", []):
            node_id = str(item.get("id"))
            nodes.append(
                TaskNode(
                    id=node_id,
                    task=item.get("task", ""),
                    role=item.get("role", "coder"),
                    metadata=item.get("metadata", {}),
                )
            )
        edges = []
        for e in data.get("edges", []):
            edges.append(TaskEdge(from_node=str(e.get("from")), to_node=str(e.get("to"))))
        graph = cls(nodes=nodes, edges=edges)
        graph.validate()
        return graph

    @classmethod
    def create_default(cls, task_objective: str, target_files: Optional[List[str]] = None) -> "TaskGraphEngine":
        target_text = ", ".join(target_files or []) or "目标文件"
        nodes = [
            TaskNode(id="1", task=f"原子化任务拆解: {task_objective[:100]}", role="planner"),
            TaskNode(id="2", task=f"实现业务代码: {target_text}", role="coder"),
            TaskNode(id="3", task="生成测试代码: system + unit", role="test_coder"),
            TaskNode(id="4", task="执行编译与测试", role="runtime"),
            TaskNode(id="5", task="失败时修复", role="fixer"),
            TaskNode(id="6", task="超限后深度诊断", role="debug_expert"),
        ]
        edges = [
            TaskEdge(from_node="1", to_node="2"),
            TaskEdge(from_node="2", to_node="3"),
            TaskEdge(from_node="3", to_node="4"),
            TaskEdge(from_node="4", to_node="5"),
            TaskEdge(from_node="5", to_node="6"),
        ]
        graph = cls(nodes=nodes, edges=edges)
        graph.validate()
        return graph

    def validate(self):
        self._node_map = {n.id: n for n in self.nodes}
        for e in self.edges:
            if e.from_node not in self._node_map:
                raise ValueError(f"TaskGraph edge from unknown node: {e.from_node}")
            if e.to_node not in self._node_map:
                raise ValueError(f"TaskGraph edge to unknown node: {e.to_node}")
        # Raise if cyclic.
        self.topological_order()

    def topological_order(self) -> List[TaskNode]:
        indegree: Dict[str, int] = {n.id: 0 for n in self.nodes}
        outgoing: Dict[str, List[str]] = {n.id: [] for n in self.nodes}
        for e in self.edges:
            indegree[e.to_node] += 1
            outgoing[e.from_node].append(e.to_node)

        queue = [nid for nid, deg in indegree.items() if deg == 0]
        ordered_ids: List[str] = []
        while queue:
            nid = queue.pop(0)
            ordered_ids.append(nid)
            for child in outgoing[nid]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

        if len(ordered_ids) != len(self.nodes):
            raise ValueError("TaskGraph contains a cycle")
        return [self._node_map[nid] for nid in ordered_ids]

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {"id": n.id, "task": n.task, "role": n.role, "metadata": n.metadata}
                for n in self.nodes
            ],
            "edges": [{"from": e.from_node, "to": e.to_node} for e in self.edges],
        }

    def save(self, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
