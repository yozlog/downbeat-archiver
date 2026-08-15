# DownBeat Archiver

[English](README.md) | [繁體中文](README.zh-TW.md)

Incrementally downloads every PDF exposed by the [DownBeat Digital Edition Archive](https://www.downbeat.com/digitaledition/archive.html), organizes issues into yearly folders, and checks for new issues every month.

## Output

```text
DownBeat/
├── 2008/
│   └── DB0908.pdf
├── 2024/
│   ├── DB24_07_Historical.pdf
│   └── DB24_07_Future.pdf
└── 2026/
    └── DB26_08.pdf
```

## Usage

### Run locally

Python 3.11 or newer is required. The tool has no runtime dependencies outside the standard library.

```bash
cd downbeat-archiver
python3 -m downbeat_archiver sync --output "$HOME/Downloads/DownBeat"
```

Install the CLI if preferred:

```bash
python3 -m pip install .
downbeat-archiver sync --output "$HOME/Downloads/DownBeat"
```

Running the same command again is safe: existing valid PDFs are reported as `SKIP` and are not downloaded again.

### Docker

One-time synchronization to any host path:

```bash
docker build -t downbeat-archiver .
docker run --rm \
  -v "$HOME/Downloads/DownBeat:/archive" \
  downbeat-archiver sync --output /archive
```

PowerShell:

```powershell
docker run --rm `
  -v "${HOME}/Downloads/DownBeat:/archive" `
  downbeat-archiver sync --output /archive
```

> [!NOTE]
> The container runs as UID `1000`. Ensure the mounted host directory is writable by that user on Linux.

## Automatic monthly synchronization

The included Compose service runs once when started, then checks on the first day of every month at 03:00 in the selected timezone.

The default `compose.yaml` pulls the prebuilt image from GitHub Container Registry:

```bash
cd downbeat-archiver
DOWNBEAT_PATH="$HOME/Downloads/DownBeat" docker compose up -d
```

To build the image locally, use `compose.build.yaml`:

```bash
cd downbeat-archiver
DOWNBEAT_PATH="$HOME/Downloads/DownBeat" \
docker compose -f compose.build.yaml up -d --build
```

To pull a newly published image and recreate the service later:

```bash
docker compose pull
docker compose up -d
```

Customize the schedule with environment variables:

```bash
DOWNBEAT_PATH="/mnt/media/DownBeat" \
SCHEDULE_DAY=5 \
SCHEDULE_HOUR=4 \
TZ="Asia/Taipei" \
docker compose up -d
```

Environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `DOWNBEAT_PATH` | `./archive` | Host path used to store PDFs |
| `SCHEDULE_DAY` | `1` | Day of the month to run, from 1 to 28 |
| `SCHEDULE_HOUR` | `3` | Hour to run, using the 24-hour clock |
| `TZ` | `Asia/Taipei` | IANA timezone used by the scheduler |

View activity with:

```bash
docker compose logs -f
```

For the local-build configuration, add `-f compose.build.yaml` to Compose commands.

Stop the service with:

```bash
docker compose down
```

The scheduler can also run without Docker:

```bash
python3 -m downbeat_archiver schedule \
  --output "$HOME/Downloads/DownBeat" \
  --day 1 \
  --hour 3 \
  --timezone Asia/Taipei
```

Add `--no-run-now` if you do not want the scheduler to synchronize immediately on startup.

## Reliability behavior

- Discovers issues from the live archive page on every synchronization.
- Skips files that already have a PDF header and a plausible size.
- Retries temporary HTTP and network errors with backoff.
- Resumes supported downloads from an existing `.part` file.
- Falls back to the newer reader's signed download when a legacy link is unavailable.
- Continues processing other issues if one issue fails and exits non-zero after a one-time sync.
- Moves completed downloads into place only after validation.

Use `--verbose` before the command for diagnostic logs:

```bash
python3 -m downbeat_archiver --verbose sync --output ./archive
```

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

## Note

AI agents are used to assist with the development and maintenance of this project.
