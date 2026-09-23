"""CLI entry point for gplot."""

import argparse
import os
import sys

import plotext as plt

from .parser import parse_grid, parse_xvg

MARKERS = ["hd", "fhd", "braille", "dot"]
COLORS = ["cyan+", "green+", "red+", "yellow", "magenta+", "orange+", "blue+", "white"]


def setup_plot(args):
    """Reset the plot state and apply width/height overrides once."""
    plt.clear_figure()
    plt.theme("dark")
    plt.clear_color()
    if args.width or args.height:
        w = args.width or plt.terminal_width()
        h = args.height or plt.terminal_height()
        plt.plot_size(w, h)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gplot",
        description="Quick terminal plotting for GROMACS .xvg files",
    )
    parser.add_argument("files", nargs="+", help=".xvg file(s) to plot")
    parser.add_argument(
        "-x",
        type=int,
        default=1,
        help="Column to use as X axis (1-based, default: 1)",
    )
    parser.add_argument(
        "-y",
        type=int,
        default=None,
        help="Column to use as Y axis (1-based, default: 2)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="plot_all",
        help="Plot all Y columns against X",
    )
    parser.add_argument(
        "--heatmap",
        action="store_true",
        help="Plot 2D heatmap from 3-column (x, y, z) grid data",
    )
    parser.add_argument(
        "--cmap",
        default="viridis",
        choices=["viridis", "plasma", "coolwarm", "bwr", "hot"],
        help="Colormap for heatmap (default: viridis)",
    )
    parser.add_argument(
        "--vmin",
        type=float,
        default=None,
        help="Min value for heatmap color scale",
    )
    parser.add_argument(
        "--vmax",
        type=float,
        default=None,
        help="Max value for heatmap color scale",
    )
    parser.add_argument(
        "-t", "--title", default=None, help="Override plot title"
    )
    parser.add_argument(
        "--xlabel", default=None, help="Override X axis label"
    )
    parser.add_argument(
        "--ylabel", default=None, help="Override Y axis label"
    )
    parser.add_argument(
        "-W",
        "--width",
        type=int,
        default=None,
        help="Plot width in characters",
    )
    parser.add_argument(
        "-H",
        "--height",
        type=int,
        default=None,
        help="Plot height in characters",
    )

    # Per-file column overrides: -f1x 1 -f1y 3 -f2x 1 -f2y 4 etc.
    # We handle these manually in parse_per_file_args
    return parser


def parse_per_file_args(argv):
    """Extract per-file column flags like -f1x, -f1y from argv.

    Returns (cleaned_argv, per_file_config) where per_file_config is
    a dict mapping file index (1-based) to {"x": int, "y": int}.
    """
    config = {}
    cleaned = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        # Match -f<N>x or -f<N>y
        if arg.startswith("-f") and len(arg) >= 4 and arg[-1] in ("x", "y"):
            num_str = arg[2:-1]
            axis = arg[-1]
            try:
                file_idx = int(num_str)
                value = int(argv[i + 1])
                config.setdefault(file_idx, {})
                config[file_idx][axis] = value
                i += 2
                continue
            except (ValueError, IndexError):
                pass
        cleaned.append(arg)
        i += 1
    return cleaned, config


def get_columns(data, col_idx):
    """Extract a column (0-based) from parsed data rows."""
    return [row[col_idx] for row in data if col_idx < len(row)]


def make_label(filepath, legend=None):
    """Create a plot label from filename and optional legend."""
    base = os.path.basename(filepath)
    if legend:
        return f"{base}: {legend}"
    return base


COLORMAPS = {
    "viridis": [
        (68, 1, 84), (72, 36, 117), (65, 68, 135), (53, 95, 141),
        (42, 120, 142), (33, 145, 140), (34, 168, 132), (68, 191, 112),
        (122, 209, 81), (189, 223, 38), (253, 231, 37),
    ],
    "plasma": [
        (13, 8, 135), (75, 3, 161), (125, 3, 168), (168, 34, 150),
        (203, 70, 121), (229, 107, 93), (248, 148, 65), (253, 195, 40),
        (240, 249, 33),
    ],
    "coolwarm": [
        (59, 76, 192), (98, 130, 234), (141, 176, 254), (184, 208, 249),
        (221, 221, 221), (245, 196, 173), (244, 154, 123), (222, 96, 77),
        (180, 4, 38),
    ],
    "bwr": [
        (0, 0, 255), (64, 64, 255), (128, 128, 255), (191, 191, 255),
        (255, 255, 255), (255, 191, 191), (255, 128, 128), (255, 64, 64),
        (255, 0, 0),
    ],
    "hot": [
        (0, 0, 0), (87, 0, 0), (173, 0, 0), (255, 0, 0),
        (255, 87, 0), (255, 173, 0), (255, 255, 0), (255, 255, 128),
        (255, 255, 255),
    ],
}


def colormap_lookup(value, vmin, vmax, cmap_name):
    """Map a scalar value to an RGB tuple using a colormap."""
    cmap = COLORMAPS[cmap_name]
    if vmax == vmin:
        t = 0.5
    else:
        t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    # Interpolate between colormap stops
    pos = t * (len(cmap) - 1)
    idx = int(pos)
    frac = pos - idx
    if idx >= len(cmap) - 1:
        return cmap[-1]
    r = int(cmap[idx][0] + frac * (cmap[idx + 1][0] - cmap[idx][0]))
    g = int(cmap[idx][1] + frac * (cmap[idx + 1][1] - cmap[idx][1]))
    b = int(cmap[idx][2] + frac * (cmap[idx + 1][2] - cmap[idx][2]))
    return (r, g, b)


def matrix_to_rgb(matrix, vmin, vmax, cmap_name):
    """Convert a 2D float matrix to a 2D RGB matrix for plotext."""
    return [
        [colormap_lookup(val, vmin, vmax, cmap_name) for val in row]
        for row in matrix
    ]


def plot_heatmap(args, filepath):
    """Plot a 2D heatmap from a 3-column grid file."""
    parsed = parse_grid(filepath)
    matrix = parsed["matrix"]
    if not matrix:
        print(f"Error: no grid data in {filepath}", file=sys.stderr)
        sys.exit(1)

    # Compute value range
    flat = [v for row in matrix for v in row]
    vmin = args.vmin if args.vmin is not None else min(flat)
    vmax = args.vmax if args.vmax is not None else max(flat)

    rgb_matrix = matrix_to_rgb(matrix, vmin, vmax, args.cmap)

    setup_plot(args)
    plt.matrix_plot(rgb_matrix)

    title = args.title or parsed.get("title")
    xlabel = args.xlabel or parsed.get("xlabel")
    ylabel = args.ylabel or parsed.get("ylabel")

    if title:
        plt.title(title)

    # Build axis tick labels from actual coordinate values
    x_vals = parsed["x_vals"]
    y_vals = parsed["y_vals"]
    nx, ny = len(x_vals), len(y_vals)

    n_xticks = 5
    n_yticks = 5
    xtick_pos = [int(i * (nx - 1) / (n_xticks - 1)) for i in range(n_xticks)]
    ytick_pos = [int(i * (ny - 1) / (n_yticks - 1)) for i in range(n_yticks)]
    plt.xticks(xtick_pos, [f"{x_vals[i]:.1f}" for i in xtick_pos])
    plt.yticks(ytick_pos, [f"{y_vals[i]:.1f}" for i in ytick_pos])

    if xlabel:
        plt.xlabel(xlabel)
    if ylabel:
        plt.ylabel(ylabel)

    # Print colorbar info as text below the plot
    zlabel = parsed.get("zlabel") or "Value"
    plt.show()
    print(f"  {zlabel}: {vmin:.3f} ", end="")
    # Print a small gradient bar
    bar_width = 30
    for i in range(bar_width):
        t = i / (bar_width - 1)
        v = vmin + t * (vmax - vmin)
        r, g, b = colormap_lookup(v, vmin, vmax, args.cmap)
        print(f"\033[48;2;{r};{g};{b}m \033[0m", end="")
    print(f" {vmax:.3f}")


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    cleaned_argv, per_file = parse_per_file_args(argv)
    parser = build_parser()
    args = parser.parse_args(cleaned_argv)

    if not args.files:
        parser.error("At least one .xvg file is required")

    if args.heatmap:
        if len(args.files) != 1:
            parser.error("--heatmap expects exactly one file")
        plot_heatmap(args, args.files[0])
        return

    parsed_files = []
    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        parsed_files.append((filepath, parse_xvg(filepath)))

    # Use metadata from the first file for defaults
    first_meta = parsed_files[0][1]

    setup_plot(args)

    series_idx = 0

    for file_num, (filepath, parsed) in enumerate(parsed_files, start=1):
        data = parsed["data"]
        if not data:
            print(f"Warning: no data in {filepath}", file=sys.stderr)
            continue

        ncols = len(data[0])

        # Determine X column for this file
        fx = per_file.get(file_num, {}).get("x", args.x)
        xcol = fx - 1  # convert to 0-based

        if xcol < 0 or xcol >= ncols:
            print(
                f"Error: X column {fx} out of range for {filepath} ({ncols} columns)",
                file=sys.stderr,
            )
            sys.exit(1)

        x_data = get_columns(data, xcol)

        if args.plot_all:
            # Plot all columns except X
            ycols = [i for i in range(ncols) if i != xcol]
        else:
            fy = per_file.get(file_num, {}).get("y", args.y or 2)
            ycol = fy - 1
            if ycol < 0 or ycol >= ncols:
                print(
                    f"Error: Y column {fy} out of range for {filepath} ({ncols} columns)",
                    file=sys.stderr,
                )
                sys.exit(1)
            ycols = [ycol]

        for ycol in ycols:
            y_data = get_columns(data, ycol)
            # xmgrace: `s0 legend` labels the first Y series (data column 1)
            legend = parsed["legends"].get(ycol - 1)
            label = make_label(filepath, legend) if (len(parsed_files) > 1 or len(ycols) > 1) else legend
            color = COLORS[series_idx % len(COLORS)]
            marker = MARKERS[series_idx % len(MARKERS)]
            plt.plot(x_data, y_data, label=label, color=color, marker=marker)
            series_idx += 1

    # Labels and title
    title = args.title or first_meta.get("title")
    xlabel = args.xlabel or first_meta.get("xlabel")
    ylabel = args.ylabel or first_meta.get("ylabel")

    if title:
        plt.title(title)
    if xlabel:
        plt.xlabel(xlabel)
    if ylabel:
        plt.ylabel(ylabel)

    plt.show()


if __name__ == "__main__":
    main()
