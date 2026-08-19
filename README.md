# KeplerSet 0.2

KeplerSet is a modern, open-source replacement for the classic **HalloKepler** element-set workflow. It runs on Microsoft Windows and macOS, authenticates with Space-Track.org, lets you build reusable satellite lists from a searchable SATCAT browser, and exports current orbital elements directly from Space-Track's modern **GP** API.

The program does not scrape the Space-Track web interface. It uses the authenticated API and keeps the Space-Track password in memory only for the current application run.

## Highlights

- Saved HalloKepler-style **element-set profiles**.
- Searchable **Space-Track SATCAT browser**.
- Add one or many catalog results directly to the current profile.
- Search by object name, NORAD catalog number, international designator, type, or country.
- Filter by object type, country, on-orbit status, launch year, inclination, and orbital period.
- SATCAT is downloaded once and cached locally; browser searches do not generate additional Space-Track requests.
- Numeric NORAD IDs are used internally, including for Alpha-5 objects.
- Optional per-object aliases for 3LE line 0 names.
- Output in every GP element representation currently documented by Space-Track:
  - TLE
  - 3LE
  - CCSDS OMM XML
  - CCSDS OMM KVN
  - JSON
  - CSV
  - HTML
- Windows GUI executable and command-line executable.
- Native macOS Apple Silicon/ARM64 GUI application and command-line executable.
- GitHub Actions builds both platforms automatically.
- No third-party runtime Python packages.

## What it replaces

A 2005 description of HalloKepler v7 describes a workflow that downloaded Space-Track data, selected orbital-element records according to a user-defined list, changed satellite names according to that list, and saved the resulting element file.

KeplerSet preserves the important parts of that workflow—lists/profiles, selection, renaming, and arbitrary output files—while replacing the old download/unpack model with direct queries to the current Space-Track API.

Historical HalloKepler description:

https://www.dl0bn.de/archiv/2005/f1305.pdf

## Space-Track API model

KeplerSet uses the current General Perturbations class:

```text
/basicspacedata/query/class/gp/...
```

for current orbital elements. Space-Track describes `gp` as the efficient current/newest SGP4 element set for each tracked object.

KeplerSet's catalog browser uses:

```text
/basicspacedata/query/class/satcat/CURRENT/Y/...
```

The complete current SATCAT response is cached on the local computer. Subsequent searches and filters operate on that cache instead of generating a Space-Track request for each search. This follows Space-Track's API guidance, which currently recommends retrieving SATCAT no more than once per day and minimizing the number of API requests.

Official Space-Track documentation:

https://www.space-track.org/documentation

## SATCAT browser

Click **Catalog…** beneath the satellite list to open the browser.

If there is no local catalog yet:

1. Enter the Space-Track identity and password in the main KeplerSet window.
2. Open **Catalog…**.
3. Click **Refresh from Space-Track**.
4. KeplerSet authenticates, downloads the current SATCAT with one query, and stores it locally.

The password is not written into the catalog cache.

### Search fields

The free-text search checks:

- NORAD catalog ID;
- Space-Track object name;
- international designator / object ID;
- object type; and
- country code.

Additional filters are available for:

- payload / rocket body / debris and other object types returned by SATCAT;
- country code;
- on-orbit objects only;
- minimum and maximum launch year;
- minimum and maximum inclination; and
- minimum and maximum orbital period.

The browser displays at most 2,000 matching rows at once to keep the GUI responsive. If more objects match, narrow the search or filters.

Select one or more results and click **Add Selected**. The **Use object name as alias** option populates the profile alias from Space-Track's current object name. Double-clicking a result also adds the selected object(s).

## Local data locations

KeplerSet stores only settings, saved profiles, and the downloaded SATCAT cache.

### Windows

```text
%APPDATA%\KeplerSet\settings.json
%APPDATA%\KeplerSet\profiles.json
%APPDATA%\KeplerSet\satcat-cache.json
```

### macOS

```text
~/Library/Application Support/KeplerSet/settings.json
~/Library/Application Support/KeplerSet/profiles.json
~/Library/Application Support/KeplerSet/satcat-cache.json
```

The Space-Track password is deliberately excluded from `settings.json` and is never persisted by KeplerSet.

## Element-set formats

| KeplerSet value | Space-Track output |
|---|---|
| `tle` | Two-line element set |
| `3le` | Name line plus two-line element set |
| `xml` | CCSDS OMM XML |
| `kvn` | CCSDS OMM KVN |
| `json` | JSON |
| `csv` | CSV |
| `html` | HTML |

KeplerSet writes the **native response supplied by Space-Track** rather than converting from a different representation. The only optional post-processing is 3LE line-0 alias replacement; TLE lines 1 and 2 remain exactly as Space-Track supplied them.

## Alpha-5 and the expanded catalog

Profiles always store numeric `NORAD_CAT_ID` values. Alpha-5 is an output convention for legacy TLE/3LE data, not a profile input format.

KeplerSet accepts TLE/3LE profiles through NORAD ID 339999 and accepts IDs through 999999999 for extensible formats. Space-Track recommends moving modern software toward extensible OMM representations such as XML, KVN, JSON, and CSV as the catalog expands.

## GUI workflow

1. Enter Space-Track credentials.
2. Create or select an element-set profile.
3. Choose the output format and destination file.
4. Add satellites manually, import/paste a list, or click **Catalog…** to search SATCAT.
5. Optionally edit aliases.
6. Click **Fetch & Export**.

Network operations run on worker threads so the GUI remains responsive.

## Importing old lists

KeplerSet accepts simple HalloKepler-style text files. Each non-comment line begins with a numeric NORAD catalog ID and can optionally contain an alias.

```text
25544 ISS
43017,AO-91
43137;AO-92
```

Whitespace, comma, semicolon, and tab separators are accepted. Lines beginning with `#` are ignored.

## Run from source

Python 3.11 or newer is required.

### Windows

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m keplerset
```

or run:

```text
run-source.bat
```

### macOS

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m keplerset
```

## Build locally

PyInstaller is used only for packaging; it is not a runtime dependency.

### Windows x64

Run either:

```text
build-windows.bat
```

or:

```powershell
.\build-windows.ps1
```

The build runs the tests first and then creates:

```text
dist\KeplerSet.exe
dist\KeplerSetCLI.exe
```

### macOS Apple Silicon / ARM64

Run on an Apple Silicon Mac:

```bash
./build-macos.sh
```

The script refuses to create the advertised ARM64 build on an Intel host. It creates:

```text
dist/KeplerSet.app
dist/KeplerSetCLI
```

PyInstaller explicitly receives `--target-arch arm64`. Without a Developer ID certificate, PyInstaller applies ad-hoc signing as required for Apple Silicon. GitHub-built artifacts are therefore not Apple-notarized releases.

## GitHub Actions

The repository contains:

```text
.github/workflows/build.yml
```

It runs on pushes to `main`, pull requests, version tags (`v*`), and manual workflow dispatches.

### Windows job

- `windows-2025` x64 GitHub-hosted runner
- Python 3.13 x64
- unit tests
- PyInstaller GUI and CLI builds
- SHA-256 hashes
- uploaded artifact: `KeplerSet-Windows-x64`

### macOS ARM64 job

- `macos-14` GitHub-hosted M1/ARM64 runner
- Python 3.13 ARM64
- unit tests
- explicit PyInstaller `--target-arch arm64`
- `file` checks that both generated executables are ARM64
- zipped `.app` bundle plus standalone CLI executable
- SHA-256 hashes
- uploaded artifact: `KeplerSet-macOS-arm64`

The workflow uses current GitHub-provided Actions major versions (`checkout@v7`, `setup-python@v7`, `upload-artifact@v7`, and `download-artifact@v8`).

### Automatic tagged releases

Pushing any tag automatically turns that workflow run into a release build. Both `0.2.2` and `v0.2.2` style tags are accepted. For example:

```bash
git tag -a 0.2.2 -m "KeplerSet 0.2.2"
git push origin 0.2.2
```

After both native build jobs succeed, the release job:

1. downloads the Windows x64 and macOS ARM64 workflow artifacts;
2. stages the GUI and CLI builds from both platforms;
3. generates a combined `SHA256SUMS.txt`;
4. creates a published GitHub Release for the pushed tag with generated release notes; and
5. uploads all built applications and the checksum file as release assets.

The published assets are:

```text
KeplerSet-Windows-x64.exe
KeplerSetCLI-Windows-x64.exe
KeplerSet-macOS-arm64.zip
KeplerSetCLI-macOS-arm64
SHA256SUMS.txt
```

The release job has job-scoped `contents: write` permission. The rest of the workflow retains `contents: read`. If the release job is rerun after a release already exists for the tag, it replaces the attached binary assets with the new build instead of creating a duplicate release.

## Command-line updates

The CLI exports a saved profile and is useful for Task Scheduler, launchd, cron-like tooling, or scripts.

```text
KeplerSetCLI.exe --profile "Amateur Satellites"
```

or on macOS:

```bash
./KeplerSetCLI --profile "Amateur Satellites"
```

Credentials may be supplied through:

```text
SPACETRACK_IDENTITY
SPACETRACK_PASSWORD
```

For example:

```powershell
$env:SPACETRACK_IDENTITY = "you@example.com"
$env:SPACETRACK_PASSWORD = "..."
.\KeplerSetCLI.exe --profile "Amateur Satellites"
```

If credentials are not supplied through the environment, the CLI prompts for them.

## Space-Track request policy

Space-Track currently publishes general API throttling limits as well as product-specific retrieval recommendations. In particular, its public documentation currently recommends:

- current GP data: no more than about once per hour; and
- SATCAT: no more than once per day, normally after 1700 UTC.

KeplerSet is designed around those constraints:

- one GP request per profile export; and
- one complete SATCAT request per manual cache refresh, followed by local searches.

Do not automate refreshes more aggressively than Space-Track permits. Consult the current Space-Track documentation and user agreement before deploying automated retrieval.

## Tests

Run:

```bash
python -m unittest discover -s tests -v
```

The test suite covers:

- numeric and Alpha-5 catalog decoding;
- 3LE alias replacement;
- HalloKepler-style list parsing;
- GP query construction;
- SATCAT query construction;
- SATCAT API record parsing;
- name/NORAD search behavior;
- object-type and orbital filtering; and
- filtering of decayed objects.

## Repository layout

```text
.github/workflows/build.yml   GitHub Windows/macOS builds
examples/                     Example lists and profiles
scripts/build.py              Common PyInstaller build driver
scripts/*_entry.py            PyInstaller-safe package entry points
src/keplerset/gui.py          Tk GUI and SATCAT browser
src/keplerset/satcat.py       SATCAT model and local search engine
src/keplerset/spacetrack.py   Authentication, GP, and SATCAT client
src/keplerset/service.py      Profile export orchestration
src/keplerset/exporters.py    Native-output writing and 3LE aliases
src/keplerset/storage.py      Profiles/settings/SATCAT cache
tests/                        Standard-library unit tests
```

## Security notes

- Passwords are not saved by KeplerSet.
- Credentials are sent only to the Space-Track login endpoint over HTTPS.
- Credentials are not embedded in GP/SATCAT query URLs.
- Logs redact identity/password path components defensively.
- GitHub Actions builds do not require or use Space-Track credentials; unit tests do not contact Space-Track.

## License

MIT. See `LICENSE`.
