# backup-helper

Create a compressed backup of a directory, record a SHA-256 manifest of every
file, verify an existing archive and rotate old backups.

## Features

- `create`: tar.gz + a `.sha256` manifest per archive, written atomically.
- `verify`: re-reads the archive and compares every file hash with the manifest.
- `rotate`: keeps the newest N archives and removes the rest.
- `list`: shows archives with size and age.
- Tests use temporary directories only.

## Installation

```bash
git clone https://github.com/victor-harden/backup-helper.git
cd backup-helper
```

## Usage

```bash
python3 backup.py create ~/projects --dest ~/backups --name projects
python3 backup.py verify ~/backups/projects-20260101T120000.tar.gz
python3 backup.py rotate ~/backups --keep 5
python3 backup.py list ~/backups
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT — see [LICENSE](LICENSE).
