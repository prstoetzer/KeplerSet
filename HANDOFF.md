# KeplerSet 0.2.2 Development Handoff

## Purpose

KeplerSet is a clean-room, modern HalloKepler-style element-set builder for Windows and macOS. It uses Space-Track's authenticated `gp` class for current elements and the `satcat` class for a locally cached searchable catalog.

## Implemented in 0.2

### SATCAT browser

- One-request current SATCAT download using `CURRENT/Y` and JSON output.
- Persistent local cache.
- No remote API call for ordinary searches.
- Free-text search across NORAD ID, object name, international designator, object type, and country.
- Filters for object type, country, on-orbit status, launch-year range, inclination range, and period range.
- Up to 2,000 displayed results per local query to avoid Tk Treeview performance problems.
- Multi-select add-to-profile.
- Optional Space-Track object name -> profile alias mapping.

### GP export

- Profile selection by numeric `NORAD_CAT_ID`.
- TLE, 3LE, XML, KVN, JSON, CSV, and HTML native output.
- 3LE line-0 alias substitution.
- Alpha-5 decoding for alias matching.
- Numeric ID validation for expanded catalog support.

### Cross-platform packaging

- Common `scripts/build.py` build driver.
- Windows batch and PowerShell wrappers.
- macOS ARM64 shell wrapper.
- GitHub Actions jobs for Windows x64 and native macOS ARM64.
- Architecture verification of generated macOS binaries.
- SHA-256 hashes generated with CI artifacts.
- Automatic GitHub Releases for pushed `v*` tags after both platform builds succeed.
- Combined release checksum manifest and rerun-safe release asset replacement.

## API endpoints

Login:

```text
POST https://www.space-track.org/ajaxauth/login
```

GP:

```text
https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/<comma-list>/orderby/NORAD_CAT_ID%20asc/format/<format>/emptyresult/show
```

SATCAT cache refresh:

```text
https://www.space-track.org/basicspacedata/query/class/satcat/CURRENT/Y/orderby/NORAD_CAT_ID%20asc/format/json/emptyresult/show
```

The SATCAT request intentionally retrieves the current catalog in one call. This is preferable to issuing a Space-Track request for every browser search and aligns with Space-Track's published recommendation to retrieve SATCAT no more than once per day.

## Storage

Windows:

```text
%APPDATA%\KeplerSet\
```

macOS:

```text
~/Library/Application Support/KeplerSet/
```

Files:

- `settings.json` — identity only, no password
- `profiles.json` — saved element-set profiles
- `satcat-cache.json` — cached SATCAT records and retrieval metadata

## Tests

Current test count: 11.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

No tests require live Space-Track credentials.

## Build notes

### Windows

`scripts/build.py` produces one-file GUI and CLI executables.

### macOS ARM64

The build explicitly uses `--target-arch arm64`. The GUI is a `.app` bundle and the CLI is a standalone executable. PyInstaller's ad-hoc signing is used unless a real signing identity is added later.

GitHub's workflow uses `macos-14`, which GitHub currently documents as an ARM64/M1 standard runner. The workflow additionally verifies the runner and output architecture instead of relying only on the runner label.

### Tagged releases

A push of any `v*` tag runs both native build jobs and, after they succeed, a dependent `release` job. The release job downloads both build artifacts, regenerates a combined `SHA256SUMS.txt`, and creates a published GitHub Release using `gh release create --verify-tag --generate-notes`. Its token permission is scoped to `contents: write`; build jobs inherit the workflow-level read-only permission.

If the release already exists (for example after rerunning a failed workflow), `gh release upload --clobber` replaces its binary assets.

## Good next iterations

1. Optional Developer ID signing and notarization in GitHub Actions when repository secrets are configured.
2. Incremental SATCAT refresh using SATCAT_DEBUT plus a periodic authoritative full refresh, if Space-Track guidance makes that appropriate.
3. Saved dynamic catalog filters that automatically rebuild a profile from the local SATCAT cache.
4. Output preview and atomic replacement/backup of existing element files.
5. Presets for SatPC32, Orbitron, GPredict, and other satellite applications.
6. Optional secure credential storage using Windows Credential Manager / macOS Keychain.
7. Optional release signing/notarization policy that can promote only signed builds when credentials are configured.

## Important constraints

- Do not turn the SATCAT browser into query-as-you-type remote calls. Keep filtering local.
- Continue using numeric NORAD IDs internally.
- Preserve native Space-Track output for all formats except the explicit 3LE alias operation.
- Do not persist the Space-Track password in plaintext settings.


## Tagged release fix (0.2.2)

The release workflow accepts any pushed tag (`tags: ["**"]`) and gates publishing with `github.ref_type == 'tag'`. This avoids the previous mismatch where a non-`v` tag could fail to trigger the release path while an ordinary `main` push still built artifacts. The release job also checks both required build results explicitly.
