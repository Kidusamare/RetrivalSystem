import builtins
import importlib
import sys
import unittest


class RetrieverImportContractTests(unittest.TestCase):
    def test_retriever_import_does_not_require_llama_index(self):
        sys.modules.pop("retrieval.retriever", None)
        sys.modules.pop("retrieval.runtime_engine", None)

        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.startswith("llama_index"):
                raise ModuleNotFoundError("No module named 'llama_index'")
            return original_import(name, globals, locals, fromlist, level)

        try:
            builtins.__import__ = guarded_import
            module = importlib.import_module("retrieval.retriever")
        finally:
            builtins.__import__ = original_import

        self.assertTrue(hasattr(module, "search_chunks"))
        self.assertTrue(callable(module.search_chunks))


if __name__ == "__main__":
    unittest.main()
