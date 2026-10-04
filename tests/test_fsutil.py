"""scripts/fsutil.py: folder wipes and copies that survive what Windows/OneDrive leaves behind."""
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import fsutil  # noqa: E402


class TestFsutil(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = os.path.join(self.tmp, "d")
        os.makedirs(os.path.join(self.dir, "sub"))
        self.file = os.path.join(self.dir, "sub", "f.txt")
        with open(self.file, "w") as f:
            f.write("old")
        os.chmod(self.file, stat.S_IREAD)

    def stuck_rmtree(self):
        """rmtree that cannot remove anything, like a folder OneDrive is holding."""
        return mock.patch.object(fsutil.shutil, "rmtree", side_effect=OSError("held"))

    def test_clear_dir_with_a_folder_that_will_not_go(self):
        with self.stuck_rmtree(), mock.patch.object(fsutil, "PAUSE", 0):
            fsutil.clear_dir(self.dir)
        self.assertTrue(os.path.isdir(self.dir))
        self.assertFalse(os.path.exists(self.file))

    def test_copy_tree_over_a_read_only_leftover(self):
        src = os.path.join(self.tmp, "src", "sub")
        os.makedirs(src)
        with open(os.path.join(src, "f.txt"), "w") as f:
            f.write("new")
        with self.stuck_rmtree(), mock.patch.object(fsutil.os, "remove", side_effect=OSError("held")), \
                mock.patch.object(fsutil, "PAUSE", 0):
            fsutil.copy_tree(os.path.dirname(src), self.dir)
        with open(self.file) as f:
            self.assertEqual(f.read(), "new")

    def test_replace_over_a_read_only_file(self):
        tmp = os.path.join(self.tmp, "t")
        with open(tmp, "w") as f:
            f.write("new")
        fsutil.replace(tmp, self.file)
        with open(self.file) as f:
            self.assertEqual(f.read(), "new")

    def test_replace_retries_while_held(self):
        real, calls = os.replace, []

        def flaky(a, b):
            calls.append(1)
            if len(calls) < 3:
                raise PermissionError("held")
            real(a, b)
        tmp = os.path.join(self.tmp, "t")
        open(tmp, "w").close()
        with mock.patch.object(fsutil.os, "replace", flaky), mock.patch.object(fsutil, "PAUSE", 0):
            fsutil.replace(tmp, self.file)
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
