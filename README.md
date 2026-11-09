# Synodic Configuration

`synodic/configuration` is a versioned [Copier](https://copier.readthedocs.io/)
overlay for existing Synodic projects. It supplies shared editor and CMake
configuration.

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
pdm run copier copy https://github.com/synodic/configuration.git .
```

The HTTPS URL is the canonical source recorded in `.copier-answers.yml`. Omit
`--vcs-ref` so Copier selects the latest stable PEP 440-compatible tag.

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

The current Renovate Copier manager accepts standard URLs and SSH-style Git
paths, but not Copier's `gh:` shortcut. Migrate after a baseline tag exists for
the consumer's recorded template commit.

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
  https://github.com/synodic/configuration.git .
```

Repeat the command without `--pretend` only after that preview is correct.
Copier then records the full HTTPS source and the matching baseline tag while
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

## Renovate automation

The hosted Renovate App can update this overlay when a consumer's answers file
contains:

```yaml
_src_path: https://github.com/synodic/configuration.git
_commit: 0.2.0
```

Renovate uses its native Copier manager to run a full template update and open a
normal pull request. Consumer repositories should require their ordinary build,
test, and conflict-marker checks. Copier artifact failures must block the update
pull request.

Automerge, when enabled, must be scoped to this Copier template only. It must
not be interpreted as approval to automerge unrelated dependency updates.

## CMake presets

When `use_cmake_presets` is enabled, the overlay renders presets from one
identity table in `includes/presets.jinja`. An identity names one
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
  command-line checks use this kind.
- Single-config fixes the configuration when configuring. Visual Studio Open
  Folder and VS Code CMake Tools both support it.
- Configurations are `debug`, `development`, and `release`. Development is
  optimized with debug information and assertions enabled. It uses the release
  runtime and Release dependencies on every platform, so it remains
  ABI-compatible with Release.
- Presets are filtered by host operating system, so each host lists only its own
  identities.

To add an identity, add one entry to `includes/presets.jinja`. Every preset
kind and configuration is generated from that entry.

## Design notes

- The overlay uses no Copier tasks or migrations, so consumers do not need
  `--trust` for normal copy or update operations.
- A second independent Copier overlay must use a separate answers file and
  explicit `--answers-file` arguments.
- The sibling `configuration` checkout is not a consumer source. Consumer
  provenance must use the canonical repository URL, never a local path.
