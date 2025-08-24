import pytest

from isekai.utils.graphs import (
    build_condensation,
    resolve_build_order,
    tarjan_scc,
    topo_sort,
)


class TestTarjanSCC:
    def test_single_node(self):
        nodes = ["a"]
        edges = []
        sccs, node_to_scc = tarjan_scc(nodes, edges)

        assert len(sccs) == 1
        assert sccs[0] == ["a"]
        assert node_to_scc["a"] == 0

    def test_two_disconnected_nodes(self):
        nodes = ["a", "b"]
        edges = []
        sccs, node_to_scc = tarjan_scc(nodes, edges)

        assert len(sccs) == 2
        assert {frozenset(scc) for scc in sccs} == {frozenset(["a"]), frozenset(["b"])}
        assert len(set(node_to_scc.values())) == 2

    def test_simple_cycle(self):
        nodes = ["a", "b", "c"]
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        sccs, node_to_scc = tarjan_scc(nodes, edges)

        assert len(sccs) == 1
        assert set(sccs[0]) == {"a", "b", "c"}
        assert node_to_scc["a"] == node_to_scc["b"] == node_to_scc["c"] == 0

    def test_acyclic_graph(self):
        nodes = ["a", "b", "c"]
        edges = [("a", "b"), ("b", "c")]
        sccs, node_to_scc = tarjan_scc(nodes, edges)

        assert len(sccs) == 3
        assert all(len(scc) == 1 for scc in sccs)
        assert len(set(node_to_scc.values())) == 3

    def test_multiple_sccs(self):
        nodes = ["a", "b", "c", "d", "e"]
        edges = [("a", "b"), ("b", "a"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "d")]
        sccs, _ = tarjan_scc(nodes, edges)

        assert len(sccs) == 3
        scc_sets = {frozenset(scc) for scc in sccs}
        expected_sets = {frozenset(["a", "b"]), frozenset(["c"]), frozenset(["d", "e"])}
        assert scc_sets == expected_sets


class TestCondensation:
    def test_single_node(self):
        edges = []
        comp_id = {"a": 0}
        k = 1
        condensation = build_condensation(edges, comp_id, k)

        assert len(condensation) == 1
        assert 0 in condensation
        assert condensation[0] == set()

    def test_two_disconnected_nodes(self):
        edges = []
        comp_id = {"a": 0, "b": 1}
        k = 2
        condensation = build_condensation(edges, comp_id, k)

        assert len(condensation) == 2
        assert condensation[0] == set()
        assert condensation[1] == set()

    def test_simple_cycle(self):
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        comp_id = {"a": 0, "b": 0, "c": 0}
        k = 1
        condensation = build_condensation(edges, comp_id, k)

        assert len(condensation) == 1
        assert 0 in condensation
        assert condensation[0] == set()

    def test_acyclic_graph(self):
        edges = [("a", "b"), ("b", "c")]
        comp_id = {"a": 0, "b": 1, "c": 2}
        k = 3
        condensation = build_condensation(edges, comp_id, k)

        assert len(condensation) == 3
        total_edges = sum(len(neighbors) for neighbors in condensation.values())
        assert total_edges == 2

    def test_multiple_sccs_with_connections(self):
        edges = [("a", "b"), ("b", "a"), ("b", "c"), ("c", "d"), ("d", "e"), ("e", "d")]
        comp_id = {"a": 0, "b": 0, "c": 1, "d": 2, "e": 2}
        k = 3
        condensation = build_condensation(edges, comp_id, k)

        assert len(condensation) == 3
        assert 1 in condensation[0]  # SCC {a,b} -> SCC {c}
        assert 2 in condensation[1]  # SCC {c} -> SCC {d,e}
        total_edges = sum(len(neighbors) for neighbors in condensation.values())
        assert total_edges == 2


class TestBuildOrder:
    def test_simple_linear_dependency(self):
        """Test a simple chain: home_page -> img_a -> favicon"""
        nodes = ["home_page", "img_a", "favicon"]
        edges = [("home_page", "img_a"), ("img_a", "favicon")]

        sccs, comp_id = tarjan_scc(nodes, edges)
        condensation = build_condensation(edges, comp_id, len(sccs))
        build_order = topo_sort(condensation)

        # Should have 3 separate components (no cycles)
        assert len(sccs) == 3
        assert all(len(scc) == 1 for scc in sccs)

        # Build order should respect dependencies
        home_comp = comp_id["home_page"]
        img_comp = comp_id["img_a"]
        favicon_comp = comp_id["favicon"]

        home_pos = build_order.index(home_comp)
        img_pos = build_order.index(img_comp)
        favicon_pos = build_order.index(favicon_comp)

        assert favicon_pos < img_pos < home_pos

    def test_no_dependencies(self):
        """Test independent resources that can be built in any order"""
        nodes = ["home_page", "about_page", "contact_page"]
        edges = []

        sccs, comp_id = tarjan_scc(nodes, edges)
        condensation = build_condensation(edges, comp_id, len(sccs))
        build_order = topo_sort(condensation)

        # Should have 3 separate components
        assert len(sccs) == 3
        assert len(build_order) == 3
        # All can be built independently
        assert len(condensation) == 3
        assert all(len(neighbors) == 0 for neighbors in condensation.values())

    def test_simple_cycle_dependency(self):
        """Test cyclic dependency that must be built together"""
        nodes = ["page_a", "page_b", "page_c"]
        edges = [("page_a", "page_b"), ("page_b", "page_c"), ("page_c", "page_a")]

        sccs, comp_id = tarjan_scc(nodes, edges)
        condensation = build_condensation(edges, comp_id, len(sccs))
        build_order = topo_sort(condensation)

        # Should have 1 component containing all nodes
        assert len(sccs) == 1
        assert set(sccs[0]) == {"page_a", "page_b", "page_c"}
        assert len(build_order) == 1

    def test_mixed_dependencies_with_scc(self):
        """Test resources with both linear dependencies and cycles"""
        nodes = ["home_page", "img_a", "img_b", "style_a", "style_b", "footer"]
        edges = [
            ("home_page", "img_a"),  # home depends on img_a
            ("img_a", "img_b"),  # img_a depends on img_b (cycle)
            ("img_b", "img_a"),  # img_b depends on img_a (cycle)
            ("img_a", "style_a"),  # img_a depends on style_a (cycle)
            ("style_a", "style_b"),  # style_a depends on style_b (cycle)
            ("style_b", "img_a"),  # style_b depends on img_a (cycle)
            ("style_a", "footer"),  # style_a depends on footer
        ]

        sccs, comp_id = tarjan_scc(nodes, edges)
        condensation = build_condensation(edges, comp_id, len(sccs))
        build_order = topo_sort(condensation)

        # Should have 3 components: {home_page}, {img_a, img_b, style_a, style_b}, {footer}
        assert len(sccs) == 3

        # Find the large SCC
        large_scc = max(sccs, key=len)
        assert len(large_scc) == 4
        assert set(large_scc) == {"img_a", "img_b", "style_a", "style_b"}

        # Verify build order respects dependencies
        home_comp = comp_id["home_page"]
        footer_comp = comp_id["footer"]
        scc_comp = comp_id["img_a"]  # All SCC members have same comp_id

        home_pos = build_order.index(home_comp)
        footer_pos = build_order.index(footer_comp)
        scc_pos = build_order.index(scc_comp)

        # Footer must be built before the SCC, SCC before home
        assert footer_pos < scc_pos < home_pos

    def test_diamond_dependency(self):
        """Test diamond-shaped dependency graph"""
        nodes = ["root", "left", "right", "leaf"]
        edges = [
            ("root", "left"),
            ("root", "right"),
            ("left", "leaf"),
            ("right", "leaf"),
        ]

        sccs, comp_id = tarjan_scc(nodes, edges)
        condensation = build_condensation(edges, comp_id, len(sccs))
        build_order = topo_sort(condensation)

        # Should have 4 separate components
        assert len(sccs) == 4

        root_comp = comp_id["root"]
        left_comp = comp_id["left"]
        right_comp = comp_id["right"]
        leaf_comp = comp_id["leaf"]

        root_pos = build_order.index(root_comp)
        left_pos = build_order.index(left_comp)
        right_pos = build_order.index(right_comp)
        leaf_pos = build_order.index(leaf_comp)

        # Leaf must come before left and right
        assert leaf_pos < left_pos
        assert leaf_pos < right_pos
        # Left and right must come before root
        assert left_pos < root_pos
        assert right_pos < root_pos

    def test_multiple_disconnected_sccs(self):
        """Test multiple separate cyclic groups"""
        nodes = ["a1", "a2", "b1", "b2", "b3", "c"]
        edges = [
            ("a1", "a2"),
            ("a2", "a1"),  # First SCC
            ("b1", "b2"),
            ("b2", "b3"),
            ("b3", "b1"),  # Second SCC
            # c is independent
        ]

        sccs, comp_id = tarjan_scc(nodes, edges)
        condensation = build_condensation(edges, comp_id, len(sccs))

        # Should have 3 components
        assert len(sccs) == 3

        # Find SCCs by size
        scc_sizes = sorted([len(scc) for scc in sccs])
        assert scc_sizes == [1, 2, 3]  # Single node, pair, triple

        # All components can be built independently
        assert all(len(neighbors) == 0 for neighbors in condensation.values())

    def test_complex_web_dependencies(self):
        """Test a more complex web-like dependency structure"""
        nodes = [
            "index",
            "navbar",
            "sidebar",
            "main_css",
            "theme_css",
            "logo",
            "bg_image",
        ]
        edges = [
            ("index", "navbar"),
            ("index", "sidebar"),
            ("index", "main_css"),
            ("navbar", "logo"),
            ("navbar", "theme_css"),
            ("sidebar", "theme_css"),
            ("main_css", "theme_css"),
            ("theme_css", "bg_image"),
            (
                "bg_image",
                "main_css",
            ),  # Creates a cycle: main_css -> theme_css -> bg_image -> main_css
        ]

        sccs, comp_id = tarjan_scc(nodes, edges)
        condensation = build_condensation(edges, comp_id, len(sccs))
        build_order = topo_sort(condensation)

        # Should identify the CSS cycle
        assert (
            len(sccs) == 5
        )  # index, navbar, sidebar, logo, {main_css, theme_css, bg_image}

        # Find the CSS SCC
        css_scc = max(sccs, key=len)
        assert len(css_scc) == 3
        assert set(css_scc) == {"main_css", "theme_css", "bg_image"}

        # Verify proper ordering
        index_comp = comp_id["index"]
        css_comp = comp_id["main_css"]  # All CSS components have same comp_id

        css_pos = build_order.index(css_comp)
        index_pos = build_order.index(index_comp)

        # CSS group must be built before index
        assert css_pos < index_pos


class TestResolveBuildOrder:
    def test_mixed_dependencies(self):
        """Test resolve_build_order with both linear dependencies and cycles"""
        nodes = ["home", "api", "cache_a", "cache_b", "config"]
        edges = [
            ("home", "api"),  # home depends on api
            ("api", "cache_a"),  # api depends on cache_a
            ("cache_a", "cache_b"),  # cache_a depends on cache_b (cycle)
            ("cache_b", "cache_a"),  # cache_b depends on cache_a (cycle)
            # config is independent
        ]

        build_groups = resolve_build_order(nodes, edges)

        # Expected: cache cycle first, then config (independent), then api, then home
        expected_groups = [
            {"cache_a", "cache_b"},  # Cycle group (order within may vary)
            {"config"},  # Independent
            {"api"},  # Depends on cache
            {"home"},  # Depends on api
        ]

        actual_groups = [set(group) for group in build_groups]
        assert actual_groups == expected_groups

    def test_unknown_node_in_edge_source(self):
        """Test error when edge references unknown source node"""
        nodes = ["a", "b"]
        edges = [("unknown", "b")]

        with pytest.raises(ValueError, match="Edge references unknown node: unknown"):
            resolve_build_order(nodes, edges)

    def test_unknown_node_in_edge_target(self):
        """Test error when edge references unknown target node"""
        nodes = ["a", "b"]
        edges = [("a", "unknown")]

        with pytest.raises(ValueError, match="Edge references unknown node: unknown"):
            resolve_build_order(nodes, edges)
