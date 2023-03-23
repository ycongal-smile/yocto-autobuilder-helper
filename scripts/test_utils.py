#!/usr/bin/env python3

import os
import unittest
import utils


class TestGetComparisonBranch(unittest.TestCase):
    TEST_CONFIG = {
        "BUILD_HISTORY_DIRECTPUSH": [
            "poky:morty",
            "poky:pyro",
            "poky:rocko",
            "poky:sumo",
            "poky:thud",
            "poky:warrior",
            "poky:zeus",
            "poky:dunfell",
            "poky:gatesgarth",
            "poky:hardknott",
            "poky:honister",
            "poky:kirkstone",
            "poky:langdale",
            "poky:master"
        ], "BUILD_HISTORY_FORKPUSH": {
            "poky-contrib:ross/mut": "poky:master",
            "poky:master-next": "poky:master",
            "poky-contrib:abelloni/master-next": "poky:master"
        }
    }

    def test_release_master(self):
        repo = "ssh://git@push.yoctoproject.org/poky"
        branch = "master"
        basebranch, comparebranch = utils.getcomparisonbranch(
            self.TEST_CONFIG, repo, branch)
        self.assertEqual(
            basebranch, "master", msg="Repo/branch pair present in BUILD_HISTORY_DIRECTPUSH must return corresponding base branch")
        self.assertEqual(
            comparebranch, None, msg="Repo/branch pair present in BUILD_HISTORY_DIRECTPUSH must return corresponding compare branch")

    def test_release_kirkstone(self):
        repo = "ssh://git@push.yoctoproject.org/poky"
        branch = "kirkstone"
        basebranch, comparebranch = utils.getcomparisonbranch(
            self.TEST_CONFIG, repo, branch)
        self.assertEqual(basebranch, "kirkstone",
                         msg="Repo/branch pair present in BUILD_HISTORY_DIRECTPUSH must return corresponding base branch")
        self.assertEqual(
            comparebranch, None, msg="Repo/branch pair present in BUILD_HISTORY_DIRECTPUSH must return corresponding compare branch")

    def test_release_langdale(self):
        repo = "ssh://git@push.yoctoproject.org/poky"
        branch = "langdale"
        basebranch, comparebranch = utils.getcomparisonbranch(
            self.TEST_CONFIG, repo, branch)
        self.assertEqual(basebranch, "langdale",
                         msg="Repo/branch pair present in BUILD_HISTORY_DIRECTPUSH must return corresponding base branch")
        self.assertEqual(
            comparebranch, None, msg="Repo/branch pair present in BUILD_HISTORY_DIRECTPUSH must return corresponding compare branch")

    def test_master_next(self):
        repo = "ssh://git@push.yoctoproject.org/poky"
        branch = "master-next"
        basebranch, comparebranch = utils.getcomparisonbranch(
            self.TEST_CONFIG, repo, branch)
        self.assertEqual(basebranch, "master-next",
                         msg="Repo/branch pair present in BUILD_HISTORY_FORKPUSH must return corresponding base branch")
        self.assertEqual(comparebranch, "master",
                         msg="Repo/branch pair present in BUILD_HISTORY_FORKPUSH must return corresponding compare branch")

    def test_abelloni_master_next(self):
        repo = "ssh://git@push.yoctoproject.org/poky-contrib"
        branch = "abelloni/master-next"
        basebranch, comparebranch = utils.getcomparisonbranch(
            self.TEST_CONFIG, repo, branch)
        self.assertEqual(basebranch, "abelloni/master-next",
                         msg="Repo/branch pair present in BUILD_HISTORY_FORKPUSH must return corresponding base branch")
        self.assertEqual(comparebranch, "master",
                         msg="Repo/branch pair present in BUILD_HISTORY_FORKPUSH must return corresponding compare branch")

    def test_ross_master_next(self):
        repo = "ssh://git@push.yoctoproject.org/poky-contrib"
        branch = "ross/mut"
        basebranch, comparebranch = utils.getcomparisonbranch(
            self.TEST_CONFIG, repo, branch)
        self.assertEqual(basebranch, "ross/mut",
                         msg="Repo/branch pair present in BUILD_HISTORY_FORKPUSH must return corresponding base branch")
        self.assertEqual(comparebranch, "master",
                         msg="Repo/branch pair present in BUILD_HISTORY_FORKPUSH must return corresponding compare branch")

    def test_arbitrary_branch(self):
        repo = "ssh://git@push.yoctoproject.org/poky-contrib"
        branch = "akanavin/package-version-updates"
        basebranch, comparebranch = utils.getcomparisonbranch(
            self.TEST_CONFIG, repo, branch)
        self.assertEqual(
            basebranch, None, msg="Arbitrary repo/branch should not return any specific basebranch")
        self.assertEqual(
            comparebranch, None,  msg="Arbitrary repo/branch should not return any specific comparebranch")

    def test_master_nightly(self):
        repo = "ssh://git@push.yoctoproject.org/poky"
        branch = "master"
        basebranch, comparebranch = utils.getcomparisonbranch(
            self.TEST_CONFIG, repo, branch)
        self.assertEqual(
            basebranch, "master", msg="Master branch should be returned")
        self.assertEqual(
            comparebranch, None,  msg="No specific comparebranch should be returned")


if __name__ == '__main__':
    unittest.main()
