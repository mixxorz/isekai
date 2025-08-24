from collections.abc import Iterable
from graphlib import TopologicalSorter

Node = str
Edge = tuple[Node, Node]


def tarjan_scc(
    nodes: Iterable[Node], edges: Iterable[Edge]
) -> tuple[list[list[Node]], dict[Node, int]]:
    """
    Tarjan's algorithm (O(V+E)) to compute strongly connected components.

    Returns:
      - comps: list of components (each is a list of original nodes)
      - comp_id: map node -> component index in `comps`
    Notes:
      - Component and member orders depend on DFS; don’t rely on them unless you sort.
    """
    # Include any endpoints that weren't listed explicitly in `nodes`
    given_order = list(nodes)
    node_set: set[Node] = set(given_order)
    for u, v in edges:
        if u not in node_set:
            given_order.append(u)
            node_set.add(u)
        if v not in node_set:
            given_order.append(v)
            node_set.add(v)

    # Build adjacency
    adj: dict[Node, list[Node]] = {n: [] for n in node_set}
    for u, v in edges:
        adj[u].append(v)

    index = 0
    stack: list[Node] = []
    on_stack: set[Node] = set()
    indices: dict[Node, int] = {}
    lowlink: dict[Node, int] = {}
    comps: list[list[Node]] = []

    def strongconnect(v: Node) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj[v]:
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        # If v is a root, pop the stack and generate an SCC
        if lowlink[v] == indices[v]:
            comp: list[Node] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            comps.append(comp)

    # Cover disconnected graphs and isolated nodes
    for v in given_order:
        if v not in indices:
            strongconnect(v)

    comp_id: dict[Node, int] = {}
    for cid, comp in enumerate(comps):
        for v in comp:
            comp_id[v] = cid

    return comps, comp_id


def build_condensation(
    edges: list[Edge], comp_id: dict[Node, int], k: int
) -> dict[int, set[int]]:
    """Return DAG as dict: comp -> set(of neighbor comps)."""
    dag: dict[int, set[int]] = {i: set() for i in range(k)}
    for u, v in edges:
        cu, cv = comp_id[u], comp_id[v]
        if cu != cv:
            dag[cu].add(cv)
    return dag


def topo_sort(dep_map: dict[int, set[int]]) -> list[int]:
    """
    Return a dependencies-first topological order of component labels.
    Raises graphlib.CycleError if dep_map itself has a cycle (shouldn't happen for condensation).
    """
    return list(TopologicalSorter(dep_map).static_order())


def resolve_build_order(
    nodes: Iterable[Node], edges: Iterable[Edge]
) -> list[list[Node]]:
    """
    Return the optimal build order for resources with dependencies.

    Returns a list of build groups, where:
    - Each group is a list of nodes that can be built in parallel
    - Groups must be built in order (dependencies first)
    - Nodes in the same group have cyclic dependencies and must be built together

    Raises ValueError if any edge references a node not in the nodes list.
    """
    node_set = set(nodes)
    for u, v in edges:
        if u not in node_set:
            raise ValueError(f"Edge references unknown node: {u}")
        if v not in node_set:
            raise ValueError(f"Edge references unknown node: {v}")

    sccs, comp_id = tarjan_scc(nodes, edges)
    condensation = build_condensation(list(edges), comp_id, len(sccs))
    build_order = topo_sort(condensation)

    # Return SCCs in topological order
    return [sccs[comp_idx] for comp_idx in build_order]
