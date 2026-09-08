import json
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

REPOSITORY_ROOT = Path(__file__).parents[1]
INSTALL_SCRIPT = REPOSITORY_ROOT / "install.sh"
MANIFEST_PATH = REPOSITORY_ROOT / "src" / "anki_ai_workspace" / "manifest.json"


class InstallScriptTests(unittest.TestCase):
    def test_clean_install_keeps_settings_when_build_fails(self) -> None:
        package_name = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["package"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            addons_directory = Path(temporary_directory) / "addons21"
            target_directory = addons_directory / package_name
            target_directory.mkdir(parents=True)
            metadata_path = target_directory / "meta.json"
            original_metadata = {"config": {"codex_executable": "/custom/codex"}}
            metadata_path.write_text(json.dumps(original_metadata), encoding="utf-8")
            fake_bin = Path(temporary_directory) / "bin"
            fake_bin.mkdir()
            fake_pgrep = fake_bin / "pgrep"
            fake_pgrep.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
            fake_pgrep.chmod(0o755)
            environment = dict(os.environ)
            environment["ANKI_ADDONS_DIR"] = str(addons_directory)
            environment["PATH"] = str(fake_bin) + os.pathsep + environment["PATH"]

            result = subprocess.run(
                [str(INSTALL_SCRIPT), "--clean", "not-a-version"],
                cwd=REPOSITORY_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(
                json.loads(metadata_path.read_text(encoding="utf-8")), original_metadata
            )
