import unittest

from ollama_status import parse_models


class OllamaStatusTests(unittest.TestCase):
    def test_parses_model_list(self):
        models = parse_models(
            {"models": [{"name": "qwen2-math:1.5b", "details": {}}]}
        )
        self.assertEqual(models[0]["name"], "qwen2-math:1.5b")

    def test_rejects_missing_models_list(self):
        with self.assertRaisesRegex(ValueError, "models list"):
            parse_models({})


if __name__ == "__main__":
    unittest.main()
