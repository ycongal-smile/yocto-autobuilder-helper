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

    test_data_is_release_version = [
        {"input": "yocto-4.2", "expected":True},
        {"input": "20230313-15", "expected":False},
        {"input": None, "expected":False}
    ]

    # This data represent real data returned by utils.getcomparisonbranch
    # and the release argument passed to send-qa-email script
    regression_inputs = [
        {"name": "Arbitrary branch", "input": {"basebranch": None,
                                               "comparebranch": None, "release": None}, "expected": (None, None)},
        {"name": "Master release", "input": {"basebranch": "master",
                                             "comparebranch": None, "release": "yocto-4.2_M3.rc1"}, "expected": ("4.2_M2", "master")},
        {"name": "Older release", "input": {"basebranch": "kirkstone",
                                            "comparebranch": None, "release": "yocto-4.0.8.rc2"}, "expected": ("yocto-4.0.7", "kirkstone")},
        {"name": "Master Next", "input": {"basebranch": "master-next",
                                          "comparebranch": "master", "release": None}, "expected": ("master", "master-next")},
        {"name": "Fork Master Next", "input": {"basebranch": "ross/mut",
                                               "comparebranch": "master", "release": None}, "expected": ("master", "ross/mut")},
    ]

    def test_versions(self):
        for data in self.test_data_get_version:
            test_name = data["input"]["version"]
            with self.subTest(f"Test {test_name} previous tag"):
                self.assertEqual(send_qa_email.get_previous_tag(os.environ.get(
                    "POKY_PATH"), data["input"]["version"]), data["expected"])

    def test_is_release_version(self):
        for data in self.test_data_is_release_version:
            with self.subTest(f"{data['input']}"):
                self.assertEqual(send_qa_email.is_release_version(data['input']), data['expected'])

    def test_get_regression_base_and_target(self):
        for data in self.regression_inputs:
            with self.subTest(data['name']):
                self.assertEqual(send_qa_email.get_regression_base_and_target(
                    data['input']['basebranch'], data['input']['comparebranch'], data['input']['release'], os.environ.get("POKY_PATH")), data['expected'])

if __name__ == '__main__':
    if os.environ.get("POKY_PATH") is None:
        print("Please set POKY_PATH to proper poky clone location before running tests")
        sys.exit(1)
    unittest.main()
