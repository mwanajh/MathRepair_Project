import unittest

from compute_allocator import allocate_compute
from mathrepair_demo import ReasoningNode


class ComputeAllocatorTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            ReasoningNode("n1", "2x + 3 = 14", ["problem"]),
            ReasoningNode("n2", "2x = 11", ["n1"]),
            ReasoningNode("n3", "x = 5.5", ["n2"]),
            ReasoningNode("n4", "14 = 2(x + 3)", ["problem"]),
            ReasoningNode("n5", "x = 4", ["n4"]),
        ]

    def test_uses_the_exact_budget_on_the_affected_branch(self):
        plans = allocate_compute(self.nodes, "n1", ["n2", "n3"], budget=10)
        calls = {plan.node_id: plan.allocated_calls for plan in plans}

        self.assertEqual(sum(calls.values()), 10)
        self.assertGreater(calls["n1"], calls["n2"])
        self.assertGreater(calls["n2"], calls["n3"])
        self.assertEqual(calls["n4"], 0)
        self.assertEqual(calls["n5"], 0)

    def test_allocates_nothing_when_there_is_no_error(self):
        plans = allocate_compute(self.nodes, None, [], budget=10)

        self.assertEqual(sum(plan.allocated_calls for plan in plans), 0)

    def test_rejects_a_negative_budget(self):
        with self.assertRaisesRegex(ValueError, "negative"):
            allocate_compute(self.nodes, "n1", ["n2"], budget=-1)


if __name__ == "__main__":
    unittest.main()
