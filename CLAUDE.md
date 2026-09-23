# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`gplot` is a CLI tool for plotting GROMACS `.xvg` files directly in the terminal using `plotext`. It parses xmgrace-style metadata (`@` lines) for titles, axis labels, and series legends.

## Install and run

```bash
pip install -e .    # editable install
gplot file.xvg      # basic usage
gplot --help         # all options
```

## Architecture

Two modules in `gplot/`:

- **`parser.py`** — `parse_xvg()` reads `.xvg` files and returns a dict with `title`, `xlabel`, `ylabel`, `legends` (dict of series index → label string), and `data` (list of float rows). `#` lines are skipped, `@` lines are parsed for metadata, everything else is numeric data.
- **`cli.py`** — `main()` is the entry point (registered in `pyproject.toml` as the `gplot` console script). Uses `argparse` for standard flags, plus custom `parse_per_file_args()` to handle `-f<N>x`/`-f<N>y` flags for per-file column selection. Columns are 1-based in the CLI, converted to 0-based internally.

## Key design details

- Per-file flags (`-f1x`, `-f1y`, `-f2x`, etc.) are extracted from `sys.argv` before argparse sees them, since argparse can't handle dynamic flag names.
- Legend index mapping follows the xmgrace convention regardless of which column the user picks as X: `@ s<N> legend` labels data column `N+1` (i.e., `s0` → data column 1). At plot time, `legends.get(ycol - 1)` resolves the label.
- Multiple series get automatically assigned distinct colors and markers from the `COLORS` and `MARKERS` lists, cycling if there are more series than options.
