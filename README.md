# Synodic Configuration

`synodic/configuration` is a versioned [Copier](https://copier.readthedocs.io/)
overlay for existing Synodic projects. It supplies shared editor and CMake
configuration, and the native check workflow for CMake projects.

The overlay does not own a consumer's:

- `pyproject.toml`
- package metadata or dependency groups
- PDM scripts
- application or library source

Consumers own their project metadata and add the small amount of project-specific
wiring needed to use this overlay.

## Quick start

Use this procedure when adding the overlay to an existing PDM project.

### Prerequisites

- Git 2.27 or newer
- Python 3.10 or newer
- PDM
- An initialized project repository with a baseline commit
- A clean project root after the baseline commit

Copier 9.17.0 or newer is required. The supported project dependency range is
`copier>=9.17,<10`.

### Apply the overlay

Run these commands from the project root:

```shell
pdm add --group config "copier>=9.17,<10"
pdm run copier copy --vcs-ref <fork-revision> gh:Behemyth/configuration .
```

Replace `<fork-revision>` with a committed revision available in the fork.
The fork is the source during development; tagged upstream releases are a
later phase.

Review any collisions with existing files. Do not use `--force` unless replacing
those files is intentional. Do not use `--trust`; this overlay contains no
unsafe tasks, migrations, or Jinja extensions.

### Add project wiring

Add these project-owned PDM scripts to `[tool.pdm.scripts]`:

```toml
config-check = "copier check-update ."
config-update = "copier update --conflict inline --skip-answered ."
```

Review and commit the Copier dependency, scripts, answers file, and generated
overlay files as one onboarding change.

A project that enables CMake presets also receives the native check workflow.
See [Native check workflow](#native-check-workflow) for the wiring it needs.

## Update the overlay

Installation and dependency synchronization do not apply Copier changes.
`pdm install`, `pdm update`, and equivalent project installers must remain
dependency-only.

### Check for an update

From the project root, run:

```shell
pdm run config-check
```

This command does not modify the project. With `--quiet`, Copier returns exit
code `0` when the project is current, `2` when an update is available, and `1`
for an error.

### Apply an update

Commit or stash unrelated work before updating. Copier's smart update requires a
clean destination tree and a Git-tracked template with a detectable version.

```shell
pdm run config-update
```

Then:

1. Review the generated diff, including `.copier-answers.yml`.
2. Resolve every inline conflict marker.
3. Review and remove any `.rej` files if rejection mode was used.
4. Run the project's build, tests, and documentation checks.
5. Commit the configuration update separately from unrelated changes.

To discard an unsuccessful update before reviewing individual files, follow
Copier's [recovery procedure](https://copier.readthedocs.io/en/stable/updating/#aborting-an-update).

## Migrate legacy provenance

Older consumers may contain this source in `.copier-answers.yml`:

```yaml
_src_path: gh:synodic/configuration
```

Migrate after a baseline tag exists for the consumer's recorded template
commit and that commit is reachable from the fork.

Run the following from a clean consumer root. The preview must mention only
`.copier-answers.yml`:

```shell
copier copy \
  --pretend \
  --vcs-ref=:current: \
  --data-file .copier-answers.yml \
  --defaults \
  --exclude "*" \
  --exclude "!.copier-answers.yml" \
  gh:Behemyth/configuration .
```

Repeat the command without `--pretend` only after that preview is correct.
Copier then records the fork source and the matching baseline tag while
preserving the existing answers. Review and commit this provenance-only change.
Use the normal update procedure for the next configuration release.

Never edit `.copier-answers.yml` directly. Copier's dedicated source migration
request is tracked in [issue #1729](https://github.com/copier-org/copier/issues/1729).

## Release contract

Configuration updates are distributed through immutable Git tags using PEP 440
versions.

Before publishing a first release:

1. Ensure every consumer baseline commit remains reachable.
2. Create one immutable tag for each required baseline commit.
3. Verify each tag resolves to the intended commit.

Do not move or reuse a published tag. Stable consumers select the latest stable
tag. `HEAD`, branches, prereleases, and raw commit references are explicit
development or recovery choices.

Every release should pass:

- the overlay render matrix for all valid answers
- a tagged consumer update test
- preservation checks for consumer-owned changes
- conflict-artifact checks
- repeat-update idempotency

## CMake presets

When `use_cmake_presets` is enabled, the overlay renders presets from one
identity table in `includes/identities.jinja`. An identity names one
ABI-distinct target: `<os>-<arch>-<toolchain>[-<variant>]`.

| Identity | Host |
|----------|------|
| `windows-x64-msvc` | Windows |
| `windows-arm64-msvc` | Windows |
| `linux-x64-clang-libcxx` | Linux |
| `linux-arm64-clang-libcxx` | Linux |
| `linux-x64-clang-libcxx-sanitize` | Linux |
| `macos-arm64-clang-libcxx` | macOS |

Each identity has two kinds of preset. Use whichever suits your editor or
workflow; they produce the same build.

| Kind | Configure preset | Build and test presets | Binary directory |
|------|------------------|------------------------|------------------|
| Ninja Multi-Config | `<identity>` | `<identity>-multi-<configuration>` | `build/<identity>/multi` |
| Ninja single-config | `<identity>-<configuration>` | `<identity>-<configuration>` | `build/<identity>/<configuration>` |

- Multi-Config configures once; choose the configuration when building. CI and
  the all-config workflow use this kind.
- Single-config fixes the configuration when configuring. Visual Studio Open
  Folder and VS Code CMake Tools both support it. Each single-config workflow
  runs configure, build, and test for that configuration.
- Configurations are `debug`, `development`, and `release`. Development is
  optimized with debug information and assertions enabled. It uses the release
  runtime and Release dependencies on every platform, so it remains
  ABI-compatible with Release. The sanitizer identity supports Debug only.
- Presets are filtered by host operating system, so each host lists only its own
  identities.
- Multi-config presets have a workflow preset named `<identity>`; run
  `cmake --workflow --preset <identity>` to configure once and build/test each
  supported configuration. Single-config workflows use the corresponding
  `<identity>-<configuration>` names.
- Every configure preset uses the committed
  `tool/cmake/dependencies.cmake` shim. It optionally includes generated,
  provider-specific search-path glue from
  `build/<identity>/deps/dependencies.cmake`; it does not select a package
  manager or replace a real CMake toolchain. Preset listing and configuration
  do not require Python or CPPython; dependencies must be prepared or
  otherwise discoverable before packages are required.
- `porr install` is the explicit environment/dependency setup step. CMake does
  not invoke Porringer, PDM, or CPPython.

The same source renders `tool/identities.toml`, which CPPython reads to select
and prepare a host identity. To add an identity, add one entry to
`includes/identities.jinja`. Every preset kind and configuration is generated
from that entry.

If CPPython uses a non-default `build-path`, set the absolute CMake cache
variable `SYNODIC_DEPENDENCIES_ROOT` to that directory. The shim then looks for
`<root>/<identity>/deps/dependencies.cmake`.

Clang locates the libc++ `import std` manifest with `-print-file-name`, which
does not search Homebrew LLVM's `lib/c++` directory. On such hosts, set the
`SYNODIC_CXX_STDLIB_MODULES_JSON` environment variable to that manifest; the
presets pass it to `CMAKE_CXX_STDLIB_MODULES_JSON`. When it is unset, CMake
detects the manifest itself.

## Native check workflow

When `use_cmake_presets` is enabled, the overlay renders
`.github/workflows/native-check.yml`. It calls the shared native check in
`Behemyth/.github`, pinned by commit, on pull requests, the merge queue, and
manual single-identity runs. It has no push or scheduled trigger.

The workflow file contains nothing project-specific:

- The manual run's identity choices come from the identity table.
- The shared check runs every identity in the project's `tool/identities.toml`.
- The shared check reads `.copier-answers.yml` to find the template revision
  the project was rendered from, and verifies the identity table against it.

The project supplies this wiring:

| Requirement | Purpose |
|-------------|---------|
| A `native` dependency group | Installed with `pdm install -G native`. It provides CPPython and the build tools. |
| A `prepare` PDM script | Prepares native dependencies for the identity in `CPPYTHON_IDENTITY`, for example `cppython install [test]`. |
| A committed `pdm.lock` | The fast stage runs `pdm lock --check`. |
| A workflow preset per identity | The overlay's presets provide these. |
| `tool/first-party.toml` (optional) | Pins Synodic packages that no remote serves yet. See the shared check's README. |

To adopt a new revision of the shared check, change the pinned commit in
`template/.github/workflows/native-check.yml.jinja`, then update each project.

## Design notes

- The overlay uses no Copier tasks or migrations, so consumers do not need
  `--trust` for normal copy or update operations.
- A second independent Copier overlay must use a separate answers file and
  explicit `--answers-file` arguments.
- Consumer provenance uses the fork source during development, never a local
  checkout path. The eventual upstream release source is a later decision.
