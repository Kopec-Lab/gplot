"""Parser for GROMACS .xvg and grid data files."""

import re

# Matches a header token, optionally followed by a "(...)" unit group,
# so "X (nm) Z (nm) Potential (V)" parses to 3 items regardless of the
# amount of whitespace between them.
_COL_TOKEN = re.compile(r"\S+(?:\s+\([^)]*\))?")


def parse_grid(filepath):
    """Parse a 3-column (x, y, z) grid file into a 2D matrix.

    Returns:
        dict with keys:
            title: str or None (from # comments)
            xlabel: str or None
            ylabel: str or None
            zlabel: str or None
            x_vals: sorted unique X values
            y_vals: sorted unique Y values
            matrix: 2D list [y][x] of Z values
    """
    title = None
    xlabel = None
    ylabel = None
    zlabel = None
    rows = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                low = line.lower()
                if "columns:" in low or "column" in low:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        cols = _COL_TOKEN.findall(parts[1])
                        if len(cols) >= 3:
                            xlabel, ylabel, zlabel = cols[0], cols[1], cols[2]
                elif title is None and not line.startswith("##"):
                    # Use first non-trivial comment as title
                    candidate = line.lstrip("# ").strip()
                    if candidate and not candidate.startswith("Grid"):
                        title = candidate
                continue
            if line.startswith("@"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
                except ValueError:
                    continue

    # Build sorted unique axes
    x_set = sorted(set(r[0] for r in rows))
    y_set = sorted(set(r[1] for r in rows))
    x_idx = {v: i for i, v in enumerate(x_set)}
    y_idx = {v: i for i, v in enumerate(y_set)}

    # Fill matrix (y rows, x columns)
    matrix = [[0.0] * len(x_set) for _ in range(len(y_set))]
    for x, y, z in rows:
        matrix[y_idx[y]][x_idx[x]] = z

    return {
        "title": title,
        "xlabel": xlabel,
        "ylabel": ylabel,
        "zlabel": zlabel,
        "x_vals": x_set,
        "y_vals": y_set,
        "matrix": matrix,
    }


def parse_xvg(filepath):
    """Parse an .xvg file and return metadata and data.

    Returns:
        dict with keys:
            title: str or None
            xlabel: str or None
            ylabel: str or None
            legends: dict mapping column index (0-based data columns) to legend string
            data: list of lists (each inner list is one row of floats)
    """
    title = None
    xlabel = None
    ylabel = None
    legends = {}
    data = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            if line.startswith("@"):
                _parse_metadata(line, legends)
                if "title" in line.lower() and title is None:
                    title = _extract_quoted(line)
                elif "xaxis" in line.lower() and "label" in line.lower():
                    xlabel = _extract_quoted(line)
                elif "yaxis" in line.lower() and "label" in line.lower():
                    ylabel = _extract_quoted(line)
                continue
            # Data line
            parts = line.split()
            try:
                row = [float(x) for x in parts]
                data.append(row)
            except ValueError:
                continue

    return {
        "title": title,
        "xlabel": xlabel,
        "ylabel": ylabel,
        "legends": legends,
        "data": data,
    }


def _extract_quoted(line):
    """Extract text between double quotes."""
    start = line.find('"')
    end = line.rfind('"')
    if start != -1 and end != -1 and start != end:
        return line[start + 1 : end]
    return None


def _parse_metadata(line, legends):
    """Parse @ lines for legend entries like '@ s0 legend "label"'."""
    stripped = line.lstrip("@ ").strip()
    if stripped.startswith("s") and "legend" in stripped:
        parts = stripped.split()
        if len(parts) >= 3 and parts[0].startswith("s") and parts[1] == "legend":
            try:
                idx = int(parts[0][1:])
            except ValueError:
                return
            label = _extract_quoted(line)
            if label:
                legends[idx] = label
