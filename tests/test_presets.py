"""Exercise the Copier identity table and the generated CMake presets."""

import json
import os
import platform
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from copier import run_copy

ROOT = Path(__file__).resolve().parents[1]


class PresetTemplateTests(unittest.TestCase):
    """Render from the working tree instead of a committed Git revision."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        shutil.copy2(ROOT / "copier.yml", self.source)
        shutil.copytree(ROOT / "includes", self.source / "includes")
        shutil.copytree(ROOT / "template", self.source / "template")

    def render(self, *, presets: bool = True, benchmarks: bool = False) -> Path:
        destination = self.root / f"project-{presets}-{benchmarks}"
        run_copy(
            str(self.source),
            destination,
            data={"use_cmake_presets": presets, "use_benchmarks": benchmarks},
            defaults=True,
            quiet=True,
        )
        return destination

    def test_all_answers_render_consistent_identity_and_preset_files(self) -> None:
        for benchmarks in (False, True):
            with self.subTest(benchmarks=benchmarks):
                project = self.render(benchmarks=benchmarks)
                rendered_table = (project / "tool" / "identities.toml").read_text(encoding="utf-8")
                self.assertTrue(rendered_table.endswith("\n"))
                self.assertFalse(rendered_table.endswith("\n\n"))
                table = tomllib.loads(rendered_table)
                self.assertEqual(table["version"], 1)
                identities = table["identities"]
                self.assertEqual(len({identity["name"] for identity in identities}), len(identities))
                self.assertEqual(len(identities), 6)

                for platform_dir, operating_system in (
                    ("windows", "windows"),
                    ("linux", "linux"),
                    ("mac", "macos"),
                ):
                    path = project / "tool" / "cmake" / "platform" / platform_dir / "CMakePresets.json"
                    rendered = path.read_text(encoding="utf-8")
                    self.assertTrue(rendered.endswith("\n"))
                    self.assertFalse(rendered.endswith("\n\n"))
                    document = json.loads(rendered)
                    configure = {preset["name"]: preset for preset in document["configurePresets"]}
                    build = {preset["name"] for preset in document["buildPresets"]}
                    test = {preset["name"] for preset in document["testPresets"]}
                    workflows = {preset["name"]: preset for preset in document["workflowPresets"]}

                    for identity in (row for row in identities if row["os"] == operating_system):
                        name = identity["name"]
                        self.assertEqual(
                            set(identity["configurations"]),
                            set(identity["dependency-build-types"]),
                        )
                        if "Development" in identity["configurations"]:
                            self.assertEqual(identity["dependency-build-types"]["Development"], "Release")
                        self.assertIn(name, configure)
                        self.assertNotIn("toolchainFile", configure[f"{name}-toolchain"])
                        self.assertIn(name, workflows)
                        for configuration in identity["configurations"]:
                            suffix = configuration.lower()
                            self.assertIn(f"{name}-{suffix}", configure)
                            self.assertIn(f"{name}-{suffix}", build)
                            self.assertIn(f"{name}-{suffix}", test)
                            self.assertIn(f"{name}-multi-{suffix}", build)
                            self.assertIn(f"{name}-multi-{suffix}", test)
                            self.assertIn(f"{name}-{suffix}", workflows)
                        if "Release" not in identity["configurations"]:
                            self.assertNotIn(f"{name}-bench", test)

                    base = configure[f"{'macos' if platform_dir == 'mac' else platform_dir}-default"]
                    includes = base["cacheVariables"]["CMAKE_PROJECT_TOP_LEVEL_INCLUDES"].split(";")
                    self.assertTrue(includes[-1].endswith("/tool/cmake/dependencies.cmake"))
                    if platform_dir == "windows":
                        self.assertEqual(len(includes), 2)
                        self.assertTrue(includes[0].endswith("/SetMSVCRuntime.cmake"))
                    else:
                        self.assertEqual(len(includes), 1)

                subprocess.run(
                    ["cmake", "--list-presets=all"],
                    cwd=project,
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def test_disabling_cmake_presets_does_not_copy_cmake_glue(self) -> None:
        project = self.render(presets=False)
        self.assertTrue((project / "tool" / "identities.toml").is_file())
        self.assertFalse((project / "CMakePresets.json").exists())
        self.assertFalse((project / "tool" / "cmake" / "dependencies.cmake").exists())

    def test_cmake_workflows_load_optional_glue_and_reject_invalid_glue(self) -> None:
        project = self.render()
        (project / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 4.0)\n"
            "project(identity_probe LANGUAGES NONE)\n"
            "if(DEFINED ENV{EXPECT_DEPENDENCIES} AND NOT PROBE_DEPENDENCIES_LOADED)\n"
            '  message(FATAL_ERROR "Dependency glue was not loaded")\n'
            "endif()\n"
            "enable_testing()\n"
            'add_test(NAME smoke COMMAND "${CMAKE_COMMAND}" -E true)\n',
            encoding="utf-8",
        )
        systems = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}
        architectures = {"AMD64": "x64", "x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}
        host_os = systems[platform.system()]
        host_arch = architectures[platform.machine()]
        table = tomllib.loads((project / "tool" / "identities.toml").read_text(encoding="utf-8"))
        identity = next(
            row
            for row in table["identities"]
            if row["os"] == host_os and row["arch"] == host_arch and not row["variant"]
        )
        name = identity["name"]

        missing = subprocess.run(
            ["cmake", "--preset", name],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Dependencies are not prepared", missing.stderr)

        glue = project / "build" / name / "deps" / "dependencies.cmake"
        glue.parent.mkdir(parents=True)
        glue.write_text('message(FATAL_ERROR "invalid dependency glue")\n', encoding="utf-8")
        invalid = subprocess.run(
            ["cmake", "--preset", f"{name}-debug"],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("invalid dependency glue", invalid.stderr)

        glue.write_text("set(PROBE_DEPENDENCIES_LOADED TRUE)\n", encoding="utf-8")
        environment = dict(os.environ, EXPECT_DEPENDENCIES="1")
        for preset in (name, *(f"{name}-{value.lower()}" for value in identity["configurations"])):
            with self.subTest(preset=preset):
                subprocess.run(
                    ["cmake", "--workflow", "--preset", preset],
                    cwd=project,
                    env=environment,
                    check=True,
                    capture_output=True,
                    text=True,
                )

        custom_root = project / "custom build"
        custom_glue = custom_root / name / "deps" / "dependencies.cmake"
        custom_glue.parent.mkdir(parents=True)
        custom_glue.write_text("set(PROBE_DEPENDENCIES_LOADED TRUE)\n", encoding="utf-8")
        subprocess.run(
            ["cmake", "--preset", name, f"-DSYNODIC_DEPENDENCIES_ROOT={custom_root}"],
            cwd=project,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        invalid_root = subprocess.run(
            ["cmake", "--preset", name, "-DSYNODIC_DEPENDENCIES_ROOT=relative"],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(invalid_root.returncode, 0)
        self.assertIn("must be an absolute path", invalid_root.stderr)


if __name__ == "__main__":
    unittest.main()
