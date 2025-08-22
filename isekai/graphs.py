from collections.abc import Hashable, Iterable

Node = Hashable
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
