# Contributing

- Use [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) messages when contributing to this repository.
- This repository generally aligns with the [Angular Commit Message Format](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit) to the extent that Releases (see below) parse commit logs to determine the type of version bump:
  - `feat`: indicates a `minor` version bump.
  - `fix`: indicates a `patch` version bump.
  - `BREAKING CHANGE:` in the commit message body indicates a `major` version bump.
- Please rebase commits in branches to the minimum necessary. Bugfix commmits (`fix: ...`) should be standalone and focused
  commits that can be back-ported to other branches via cherry-picking.

# Release Management

This project is developed using a Trunk-Based Development pattern, where the trunk branch is named `main`.
Developers should work in short-lived feature branches and commit their work to the trunk in accordance with
the [LSST Development Workflow](https://developer.lsst.io/work/flow.html).

Releases are performed at an unspecified cadence, to be no shorter than 1 week and subject to these rules:

- Releases are named according to their semantic version (major.minor.patch).
- Releases are made by adding a named tag to the trunk branch.
- Each release will increment the minor version and set the patch level to 0, e.g., `1.0.12` -> `1.1.0`
- If a bugfix commit in the trunk needs to be added to a release, then a retroactive branch will be created from the affected release tag; any fix commits are cherry-picked into the release branch and a new tag is written with an incremented patch level, e.g., `1.23.0` -> `1.23.1`. This release branch is never merged to `main` (trunk) but is kept for subsequent cherry-picked fixes.
- The major version is incremented only in the presence of user-facing breaking changes.

This project uses `python-semantic-release` to manage releases. A release may be triggered by any ticket branch
being merged into `main`. A release must increment the application version according to semantic versioning (i.e.,
the use of major-minor-patch version tokens); and must create a matching git tag.

A manual release may be made on any ticket branch ending in `release`, e.g., `tickets/DM-XXXXX/release` by using
the make targets described below.

The `make release` target is designed to shepherd the manual release management process:

1. The version number in `src/lsst/cmservice/__init__.py:__version__` is written according to the new version.
1. The updated version file is committed to git.
1. A tag is created for the current release commit.

The `make signed-release` target does the above but creates a *signed* tag, so only authors with
correct GPG keys may create a signed release.

*Take care to push release tags (signed or not) only after the release branch has been merged to main.*

A pre-release may be made in a `u/*` or a `ticket/*` branch by calling `make release`, and the version will be
bumped according to pre-release rules.
