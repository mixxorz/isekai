from isekai.graphs import tarjan_scc


class TestTarjanSCC:
    def test_single_node(self):
        nodes = [1]
        edges = []
        sccs, node_to_scc = tarjan_scc(nodes, edges)

        assert len(sccs) == 1
        assert sccs[0] == [1]
        assert node_to_scc[1] == 0

    def test_two_disconnected_nodes(self):
        nodes = [1, 2]
        edges = []
        sccs, node_to_scc = tarjan_scc(nodes, edges)

        assert len(sccs) == 2
        assert {frozenset(scc) for scc in sccs} == {frozenset([1]), frozenset([2])}
        assert len(set(node_to_scc.values())) == 2

    def test_simple_cycle(self):
        nodes = [1, 2, 3]
        edges = [(1, 2), (2, 3), (3, 1)]
        sccs, node_to_scc = tarjan_scc(nodes, edges)

        assert len(sccs) == 1
        assert set(sccs[0]) == {1, 2, 3}
        assert node_to_scc[1] == node_to_scc[2] == node_to_scc[3] == 0

    def test_acyclic_graph(self):
        nodes = [1, 2, 3]
        edges = [(1, 2), (2, 3)]
        sccs, node_to_scc = tarjan_scc(nodes, edges)

        assert len(sccs) == 3
        assert all(len(scc) == 1 for scc in sccs)
        assert len(set(node_to_scc.values())) == 3

    def test_multiple_sccs(self):
        nodes = [1, 2, 3, 4, 5]
        edges = [(1, 2), (2, 1), (2, 3), (3, 4), (4, 5), (5, 4)]
        sccs, _ = tarjan_scc(nodes, edges)

        assert len(sccs) == 3
        scc_sets = {frozenset(scc) for scc in sccs}
        expected_sets = {frozenset([1, 2]), frozenset([3]), frozenset([4, 5])}
        assert scc_sets == expected_sets
