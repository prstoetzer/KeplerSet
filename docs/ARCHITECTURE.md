# KeplerSet Architecture

KeplerSet intentionally separates remote data acquisition from local catalog browsing.

## Components

`spacetrack.py` owns authenticated HTTPS communication with Space-Track. It exposes GP retrieval for profiles and a single current-SATCAT retrieval operation.

`satcat.py` converts SATCAT JSON rows into typed `SatcatRecord` objects and implements all browser matching/filtering locally.

`storage.py` persists profiles, non-secret settings, and the SATCAT cache using atomic JSON-file replacement.

`gui.py` contains the main profile editor and the SATCAT browser dialog. Network operations run in worker threads and communicate with Tk through queues polled from the GUI thread.

`service.py` orchestrates a profile export. `exporters.py` writes native response bytes and performs the optional 3LE line-0 alias replacement.

## Why the SATCAT browser is cache-first

Space-Track's public API guidance recommends retrieving SATCAT no more than once per day and minimizing individual object queries. A typical search-as-you-type implementation would violate the spirit of that guidance and make the GUI dependent on network latency.

KeplerSet therefore downloads the current catalog once, saves it locally, and runs arbitrary searches on the cached records. The design also allows the catalog browser to remain useful when Space-Track is temporarily unavailable.

## Authentication

A `SpaceTrackClient` has a cookie jar and authenticated URL opener. Login credentials are posted to `/ajaxauth/login`. Subsequent API GETs use the resulting session cookies. Passwords are never written by the storage module.

## Build model

PyInstaller builds must run on the target OS. The GitHub workflow therefore has independent Windows and macOS jobs.

The macOS job runs on native ARM64 hardware and sets PyInstaller's target architecture to `arm64`. This avoids accidentally producing an Intel build under Rosetta and provides a direct failure if an incompatible binary dependency is introduced later.
