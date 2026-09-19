import unittest

from mathrepair_demo import ReasoningNode
from reasoning_graph import analyze_graph, topological_order


class AnalyzeGraphTests(unittest.TestCase):
    def test_error_affects_only_its_branch(self):
        nodes = [
            ReasoningNode("n1", "2x + 3 = 14", ["problem"]),
            ReasoningNode("n2", "2x = 11", ["n1"]),
            ReasoningNode("n3", "x = 5.5", ["n2"]),
            ReasoningNode("n4", "14 = 2(x + 3)", ["problem"]),
            ReasoningNode("n5", "x = 4", ["n4"]),
        ]

        analysis = analyze_graph("2(x + 3) = 14", nodes)

        self.assertEqual(analysis.error_node_id, "n1")
        self.assertEqual(analysis.affected_node_ids, ["n2", "n3"])
        self.assertNotIn("n4", analysis.affected_node_ids)
        self.assertNotIn("n5", analysis.affected_node_ids)

    def test_orders_parent_before_child(self):
        nodes = [
            ReasoningNode("child", "x = 4", ["parent"]),
            ReasoningNode("parent", "2x = 8", ["problem"]),
        ]

        ordered = topological_order(nodes)

        self.assertEqual([node.node_id for node in ordered], ["parent", "child"])

    def test_rejects_a_cycle(self):
        nodes = [
            ReasoningNode("n1", "x = 4", ["n2"]),
            ReasoningNode("n2", "2x = 8", ["n1"]),
        ]

        with self.assertRaisesRegex(ValueError, "cycle"):
            topological_order(nodes)


if __name__ == "__main__":
    unittest.main()
