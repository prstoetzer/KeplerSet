# Changelog

## 0.2.2 - 2026-08-19

- Fixed tagged-release gating so **any pushed tag** triggers the release path, not only tags beginning with `v`.
- Release job now uses `github.ref_type == 'tag'` and explicitly checks that both native build jobs succeeded.
- Added `always()` to the release job condition so dependency evaluation is explicit while still refusing to publish if either platform build fails.
- Synchronized the package `__version__` value with project metadata.


## 0.2.1 - 2026-08-19

- Added automatic GitHub Release publication for pushed `v*` tags.
- Tagged builds now wait for both Windows x64 and macOS ARM64 jobs to succeed before publishing.
- Release assets include both GUI builds, both CLI builds, and a combined SHA-256 checksum file.
- Added idempotent release reruns: an existing release has its binary assets replaced with the newly built copies.
- Scoped release-time `GITHUB_TOKEN` access to `contents: write`; ordinary build jobs remain read-only.
- Updated GitHub artifact actions to `upload-artifact@v7` and added `download-artifact@v8` for release assembly.

## 0.2.0 - 2026-08-19

- Added a searchable local Space-Track SATCAT browser.
- Added one-request current SATCAT cache refresh.
- Added name, NORAD ID, international-designator, type, country, launch-year, inclination, period, and on-orbit filtering.
- Added multi-select insertion from SATCAT into the current element-set profile.
- Added optional Space-Track object-name aliases.
- Added native macOS Apple Silicon/ARM64 support.
- Added shared PyInstaller build driver.
- Added GitHub Actions builds for Windows x64 and macOS ARM64.
- Added macOS output architecture verification and SHA-256 hashes.
- Updated application data paths for macOS.
- Expanded automated tests from 5 to 11.

## 0.1.0 - 2026-08-19

- Initial HalloKepler replacement.
- Saved profiles and manual/imported satellite lists.
- Space-Track GP API support.
- TLE, 3LE, XML, KVN, JSON, CSV, and HTML output.
- 3LE alias replacement and Alpha-5 support.
- Windows GUI and CLI PyInstaller builds.
