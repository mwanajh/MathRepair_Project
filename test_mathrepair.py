import unittest

from mathrepair_demo import verify_user_step


class VerifyUserStepTests(unittest.TestCase):
    def test_detects_wrong_distribution(self):
        ok, error_type, repair, answer = verify_user_step(
            "2(x + 3) = 14", "2x + 3 = 14"
        )

        self.assertFalse(ok)
        self.assertEqual(error_type, "algebraic_transformation_error")
        self.assertEqual(repair, "2x + 6 = 14")
        self.assertEqual(answer, "x = 4")

    def test_accepts_equivalent_step(self):
        ok, error_type, repair, answer = verify_user_step(
            "2(x + 3) = 14", "2x + 6 = 14"
        )

        self.assertTrue(ok)
        self.assertEqual(error_type, "")
        self.assertEqual(repair, "2x + 6 = 14")
        self.assertEqual(answer, "x = 4")

    def test_detects_arithmetic_error(self):
        ok, error_type, repair, answer = verify_user_step(
            "7 + 5 = 12", "7 + 5 = 13"
        )

        self.assertFalse(ok)
        self.assertEqual(error_type, "arithmetic_error")
        self.assertEqual(repair, "7 + 5 = 12")
        self.assertEqual(answer, "true")

    def test_repairs_distribution_example(self):
        ok, error_type, repair, answer = verify_user_step(
            "3(x + 2) = 15", "3x + 2 = 15"
        )

        self.assertFalse(ok)
        self.assertEqual(error_type, "algebraic_transformation_error")
        self.assertEqual(repair, "3x + 6 = 15")
        self.assertEqual(answer, "x = 3")

    def test_detects_sign_error(self):
        ok, error_type, repair, answer = verify_user_step(
            "x - 5 = 2", "x = -3"
        )

        self.assertFalse(ok)
        self.assertEqual(error_type, "sign_error")
        self.assertEqual(repair, "x = 7")
        self.assertEqual(answer, "x = 7")


if __name__ == "__main__":
    unittest.main()
