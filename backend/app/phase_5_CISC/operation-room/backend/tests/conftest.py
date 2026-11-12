import inspect
import unittest


_ORIGINAL_LOAD = unittest.TestLoader.loadTestsFromTestCase


def _shim_non_unittest_class(test_case_class):
    methods = {}
    for name, member in inspect.getmembers(test_case_class):
        if name.startswith("test") and callable(member):
            # Check for pytest skip/skipif marks
            pytest_marks = getattr(member, "pytestmark", [])
            should_skip = False
            for mark in pytest_marks:
                if mark.name in ("skip", "skipif"):
                    # Check condition if it's skipif
                    if mark.name == "skipif" and len(mark.args) > 0 and not mark.args[0]:
                        continue # condition is False, don't skip
                    should_skip = True
                    break
            if should_skip:
                methods[name] = unittest.skip("pytest mark skipped")(member)
            else:
                methods[name] = member
            
    if not methods:
        return None
    return type(f"{test_case_class.__name__}Shim", (unittest.TestCase,), methods)


def _patched_load_tests_from_testcase(self, testCaseClass):
    if isinstance(testCaseClass, type) and not issubclass(testCaseClass, unittest.TestCase):
        shim = _shim_non_unittest_class(testCaseClass)
        if shim is not None:
            return _ORIGINAL_LOAD(self, shim)
    return _ORIGINAL_LOAD(self, testCaseClass)


def pytest_configure(config):
    unittest.TestLoader.loadTestsFromTestCase = _patched_load_tests_from_testcase


def pytest_unconfigure(config):
    unittest.TestLoader.loadTestsFromTestCase = _ORIGINAL_LOAD
