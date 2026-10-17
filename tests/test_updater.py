"""Updater tests for ZIP installs (Instalar.bat): no network, no restart, temp folders only."""
import io
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import updater  # noqa: E402

SHA_OLD = "a" * 40
SHA_NEW = "b" * 40


def github_zip(files: dict, root="Daily_Personal_Gamification-" + SHA_NEW) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(root + "/", "")
        for name, content in files.items():
            zf.writestr(f"{root}/{name}", content)
    return buf.getvalue()


class ZipUpdateTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        # every test works on a temp copy: the updater must never write into the real project folder here
        repo = mock.patch.object(updater, "REPO", self.dir)
        repo.start()
        self.addCleanup(repo.stop)
        (self.dir / "main.py").write_text("old main")
        (self.dir / "requirements.txt").write_text("flet==1.0.0\n")
        (self.dir / "local_only.txt").write_text("keep me")
        (self.dir / ".venv").mkdir()
        (self.dir / ".venv" / "marker").write_text("venv")

    def test_apply_overwrites_adds_and_never_deletes_or_touches_venv(self):
        changed = updater.apply_zip(github_zip({
            "main.py": "new main", "assets/icon.ico": "ico", "requirements.txt": "flet==1.0.0\n",
            ".venv/marker": "evil", "__pycache__/x.pyc": "junk",
        }), self.dir)
        self.assertFalse(changed)
        self.assertEqual((self.dir / "main.py").read_text(), "new main")
        self.assertEqual((self.dir / "assets" / "icon.ico").read_text(), "ico")
        self.assertEqual((self.dir / "local_only.txt").read_text(), "keep me")
        self.assertEqual((self.dir / ".venv" / "marker").read_text(), "venv")
        self.assertFalse((self.dir / "__pycache__").exists())

    def test_requirements_change_is_reported(self):
        self.assertTrue(updater.apply_zip(github_zip({"requirements.txt": "flet==1.0.1\n"}), self.dir))

    def test_paths_outside_the_folder_are_ignored(self):
        updater.apply_zip(github_zip({"../escape.txt": "x", "ok.txt": "y"}), self.dir)
        self.assertFalse((self.dir.parent / "escape.txt").exists())
        self.assertTrue((self.dir / "ok.txt").exists())

    def _run_update(self, latest, installed=None, requirements="flet==1.0.0\n"):
        if installed:
            (self.dir / updater.VERSION_FILE).write_text(installed)
        with mock.patch.object(updater, "REPO", self.dir), \
                mock.patch.object(updater, "_latest_commit", return_value=latest), \
                mock.patch.object(updater, "_download_zip",
                                  return_value=github_zip({"main.py": "new", "requirements.txt": requirements})) as dl, \
                mock.patch.object(updater, "_pip_install") as pip, \
                mock.patch.object(updater, "_restart") as restart:
            updater.check_for_updates()
        return dl, pip, restart

    def test_up_to_date_does_nothing(self):
        dl, pip, restart = self._run_update(SHA_OLD, installed=SHA_OLD)
        dl.assert_not_called()
        restart.assert_not_called()

    def test_new_version_is_applied_recorded_and_restarted(self):
        dl, pip, restart = self._run_update(SHA_NEW, installed=SHA_OLD)
        dl.assert_called_once_with(SHA_NEW)
        self.assertEqual((self.dir / "main.py").read_text(), "new")
        self.assertEqual((self.dir / updater.VERSION_FILE).read_text(), SHA_NEW)
        pip.assert_not_called()  # same requirements
        restart.assert_called_once()

    def test_first_run_after_install_updates_and_installs_new_requirements(self):
        dl, pip, restart = self._run_update(SHA_NEW, requirements="flet==2.0.0\n")
        pip.assert_called_once()
        restart.assert_called_once()

    def test_offline_starts_normally(self):
        with mock.patch.object(updater, "REPO", self.dir), \
                mock.patch.object(updater, "_latest_commit", side_effect=OSError("offline")), \
                mock.patch.object(updater, "_restart") as restart:
            updater.check_for_updates()
        restart.assert_not_called()
        self.assertEqual((self.dir / "main.py").read_text(), "old main")

    def test_git_clones_keep_using_git(self):
        (self.dir / ".git").mkdir()
        with mock.patch.object(updater, "REPO", self.dir), \
                mock.patch.object(updater, "_git_update") as git, \
                mock.patch.object(updater, "_zip_update") as zip_update:
            updater.check_for_updates()
        git.assert_called_once()
        zip_update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
