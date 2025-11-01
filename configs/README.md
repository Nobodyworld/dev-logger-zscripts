# Configuration Assets

Configuration files that influence runtime behaviour live in this directory. The
primary file, `zscripts.config.json`, mirrors the defaults embedded in
`zscripts/config.py` and powers legacy scripts that still expect JSON-driven
configuration.

Runtime overrides can also be loaded through `python cli.py --config <file>`.
See `README.md` for end-to-end usage instructions and `SPEC.md` for governance
rules around configuration management.
