#!/usr/bin/env python3
"""
Test suite for send_qa_email.py

The suite needs a valid poky clone to run since it will
fetch and return revisions from remote repository. To run the suite,
set POKY_PATH environment variable accordingly:
`POKY_PATH=~/src/poky ./scripts/test_send_qa_email.py`
"""
import os
import sys
import unittest
import send_qa_email


class TestVersion(unittest.TestCase):
    test_data_get_version = [
        {"input": {"version": "4.1.2"}, "expected": "yocto-4.1.1"},
        {"input": {"version": "4.1"}, "expected": "yocto-4.0"},
        {"input": {"version": "4.1.1"}, "expected": "yocto-4.1"},
        {"input": {"version": "4.1_M2"}, "expected": "4.1_M1"},
        {"input": {"version": "4.1_M1"}, "expected": "yocto-4.0"},
        {"input": {"version": "4.1.1.rc1"}, "expected": "yocto-4.1"},
        {"input": {"version": "4.1.2.rc1"}, "expected": "yocto-4.1.1"},
        {"input": {"version": "4.1_M3.rc1"}, "expected": "4.1_M2"},
        {"input": {"version": "4.1_M3.rc4"}, "expected": "4.1_M2"},
        {"input": {"version": "4.1_M1.rc1"}, "expected": "yocto-4.0"},
        {"input": {"version": "4.1_M1.rc4"}, "expected": "yocto-4.0"},
        {"input": {"version": "4.1.rc4"}, "expected": "yocto-4.0"}
    ]

    test_data_get_sha1 = [
        {"input": "yocto-4.0", "expected": "00cfdde791a0176c134f31e5a09eff725e75b905"},
        {"input": "4.1_M1", "expected": "95066dde6861ee08fdb505ab3e0422156cc24fae"},
    ]

    def test_versions(self):
        for data in self.test_data_get_version:
            test_name = data["input"]["version"]
            with self.subTest(f"Test {test_name} previous tag"):
                self.assertEqual(send_qa_email.get_previous_tag(os.environ.get(
                    "POKY_PATH"), data["input"]["version"]), data["expected"])

    def test_get_sha1(self):
        for data in self.test_data_get_sha1:
            test_name = data["input"]
            with self.subTest(f"Test SHA1 from {test_name}"):
                self.assertEqual(send_qa_email.get_sha1(os.environ.get(
                    "POKY_PATH"), data["input"]), data["expected"])


if __name__ == '__main__':
    if os.environ.get("POKY_PATH") is None:
        print("Please set POKY_PATH to proper poky clone location before running tests")
        sys.exit(1)
    unittest.main()
