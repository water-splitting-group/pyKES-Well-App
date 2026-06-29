"""
FirePlate Oxygen Recalculation Script
======================================
Calibration data is read directly from the measurement file (the
"#Calibration" sections) instead of a separate calibration CSV.
Experimental data columns are located dynamically by content rather than
by fixed position, so the script tolerates files with a varying number
of wells/channels.

Public entry point: process_oxygen_data(directory, metadata_dict, well_mapping_file=...)
"""

from pathlib import Path
import re
import warnings

import pandas as pd
from pyrotoolbox.oxygen import calculate_pO2_from_calibration, hPa_to_uM


# ---------------------------------------------------------------------------
# Optional metadata_dict override keys
# ---------------------------------------------------------------------------
# If present in metadata_dict, this key lets the caller restrict which
# "Optical Temp" channels (within the well's measurement group) are
# averaged together to obtain the temperature used for the O2 calculation.
# Value should be a list of well/channel identifiers as they appear in the
# column brackets, e.g. ["A2", "A4"]. If the key is absent or empty, ALL
# "Optical Temp" channels found in the well's group are averaged (default).
OPTICAL_TEMPERATURE_CHANNELS_KEY = "optical_temperature_channels"


# ---------------------------------------------------------------------------
# Calibration parsing
# ---------------------------------------------------------------------------

# Maps a *normalized* calibration header label (see _normalize) to the key
# expected in the calibration dict consumed by calculate_pO2_from_calibration.
# Normalization strips everything except lowercase letters/digits, so this
# mapping is robust to encoding issues with special characters (e.g. "°", "%").
_CALIBRATION_FIELD_MAP = {
    "dphi100": "dphi100",                     # "dphi 100% (°)"
    "dphi0": "dphi0",                         # "dphi 0% (°)"
    "f": "f",                                 # "f"
    "m": "m",                                 # "m"
    "ttk": "tt",                              # "tt(%/K)"
    "ktk": "kt",                              # "kt(%/K)"
    "mt1k": "mt",                             # "mt(1/K)"
    "temperaturec": "temp100",                # "Temperature (°C)"
    "temperaturecat0": "temp0",               # "Temperature (°C) at 0%"
    "airpressurembar": "pressure",            # "Air Pressure (mbar)"
    "humidityrh": "humidity",                 # "Humidity (%RH)"
    "partialvolumeofoxygeno2": "percentO2",   # "Partial Volume of Oxygen (%O2)"
    "tofsk": "Tofs",                          # "Tofs(K)"
    "ksv1mbar": "Ksv",                        # "Ksv (1/mbar)"
}
_FT_NORMALIZED_KEY = "ft"

_SECTION_END_PATTERN = re.compile(r"^#-{2,}")
_CALIBRATION_START_PATTERN = re.compile(r"^#Calibration\b", re.IGNORECASE)


def _normalize(label):
    """Lowercase and strip everything but letters/digits, for robust matching
    of header labels regardless of encoding artifacts (degree signs, %, etc.)."""
    return re.sub(r"[^a-z0-9]", "", label.lower())


def parse_calibration_section(lines, well):
    """
    Scan the raw lines of the data file for a '#Calibration' block that
    contains a row for `well`, and return the calibration dict for that well.

    Expected layout:
        #Calibration:<TAB>WellNr<TAB>lastCal1<TAB>...<TAB><last column>
        #<TAB><well><TAB><value1><TAB>...<TAB><last value>
        #<TAB><other_well><TAB>...
        #---<anything>            <- end of this block

    There may be several such blocks in the file (one per group of wells).
    Each well appears in exactly one block, so the first block in which the
    well is found is used; scanning stops there.

    Raises
    ------
    ValueError
        If no calibration row for `well` is found anywhere in the file.
    """
    header_cols = None  # normalized header labels for the current block
    raw_header_cols = None

    for raw_line in lines:
        line = raw_line.rstrip("\n")

        if _CALIBRATION_START_PATTERN.match(line):
            # New calibration block starts here.
            cells = line.split("\t")
            raw_header_cols = [c.strip() for c in cells[1:]]
            header_cols = [_normalize(c) for c in raw_header_cols]
            continue

        if _SECTION_END_PATTERN.match(line):
            # End of whatever block (if any) we were in.
            header_cols = None
            raw_header_cols = None
            continue

        if header_cols is None:
            continue

        if not line.startswith("#"):
            # Stray non-'#' line inside what should be a calibration block;
            # ignore it rather than mis-parsing it as a calibration row.
            continue

        values = [v.strip() for v in line.split("\t")[1:]]
        if not values:
            continue

        row_well = values[0]
        if row_well != well:
            continue

        # Found the row for our well.
        row = dict(zip(header_cols, values))
        return _build_calibration_dict(row, raw_header_cols, header_cols, well)

    raise ValueError(
        f"No '#Calibration' block contains a row for well '{well}'."
    )


def _build_calibration_dict(row, raw_header_cols, header_cols, well):
    """Translate a parsed calibration row (normalized header -> raw value)
    into the calibration dict expected by calculate_pO2_from_calibration."""
    calibration = {}
    missing = []

    for normalized_label, target_key in _CALIBRATION_FIELD_MAP.items():
        if normalized_label in row:
            try:
                calibration[target_key] = float(row[normalized_label])
            except ValueError:
                missing.append(target_key)
        else:
            missing.append(target_key)

    if missing:
        raise ValueError(
            f"Calibration row for well '{well}' is missing expected field(s): "
            f"{missing}. Available header columns: {raw_header_cols}"
        )

    # 'tt' and 'kt' are given in %/K in the file but need to be used as
    # fractional units (i.e. divided by 100).
    for key in ("tt", "kt"):
        calibration[key] = calibration[key] / 100.0

    # 'ft' has no equivalent column in the new calibration line; fall back
    # to 0.0 with a warning if it's genuinely absent, but still pick it up
    # if a future file format does include it.
    if _FT_NORMALIZED_KEY in row:
        calibration["ft"] = float(row[_FT_NORMALIZED_KEY])
    else:
        warnings.warn(
            f"Calibration parameter 'ft' not found for well '{well}'; "
            f"defaulting to 0.0."
        )
        calibration["ft"] = 0.0

    return calibration


# ---------------------------------------------------------------------------
# Experimental data header parsing
# ---------------------------------------------------------------------------

_BRACKET_TAG_PATTERN = re.compile(r"\[(.*?)\]")


def _bracket_tag(col_name):
    match = _BRACKET_TAG_PATTERN.search(col_name)
    return match.group(1) if match else None


def _find_column(columns, *required_substrings, exclude=()):
    """
    Return the first column (in header order) whose name contains every
    string in `required_substrings` (case-insensitive) and none of `exclude`.
    Warns if more than one column matches, and uses the first match.
    """
    matches = [
        col for col in columns
        if all(s.lower() in col.lower() for s in required_substrings)
        and not any(s.lower() in col.lower() for s in exclude)
    ]
    if not matches:
        raise ValueError(
            f"No column found containing {required_substrings} "
            f"(excluding {exclude}). Available columns: {columns}"
        )
    if len(matches) > 1:
        warnings.warn(
            f"Multiple columns match {required_substrings}: {matches}. "
            f"Using the first one: '{matches[0]}'."
        )
    return matches[0]


def _find_columns_all(columns, *required_substrings, exclude=()):
    """
    Return ALL columns (in header order) whose name contains every string in
    `required_substrings` (case-insensitive) and none of `exclude`. Unlike
    `_find_column`, this is used where multiple matches are expected and
    wanted (e.g. averaging several optical temperature channels).
    """
    matches = [
        col for col in columns
        if all(s.lower() in col.lower() for s in required_substrings)
        and not any(s.lower() in col.lower() for s in exclude)
    ]
    if not matches:
        raise ValueError(
            f"No column found containing {required_substrings} "
            f"(excluding {exclude}). Available columns: {columns}"
        )
    return matches


_GROUP_NUMBER_PATTERN = re.compile(r"Gr\.(\d+)")


def find_experimental_columns(header_cols, well, optical_channels=None):
    """
    Locate the columns needed for processing a single well's oxygen data:
      - dphi column for this well        (contains 'dphi' and the well name)
      - dt column for the well's group   (contains 'dt' and 'Gr.<N>')
      - Optical Temp column(s) for that group (contains 'Optical' and 'Gr.<N>')
    plus the Date/Time columns that share the same measurement group as the
    dt column (so the index is built from the matching timestamp).

    The group number <N> is not assumed to be 2 - it is read from the well's
    own dphi column, so wells assigned to any of the device's groups
    (Gr.1 .. Gr.4) are handled the same way.

    Parameters
    ----------
    optical_channels : list of str, optional
        If given, only "Optical Temp" columns whose name contains one of
        these identifiers (e.g. ["A2", "A4"]) are used. If None or empty,
        ALL "Optical Temp" columns found in the well's group are used.
        See OPTICAL_TEMPERATURE_CHANNELS_KEY.

    Returns
    -------
    dict with keys: 'dphi', 'dt', 'optical_temperature', 'date', 'time'.
    'optical_temperature' is a LIST of one or more raw column names (to be
    averaged); all other values are single raw column names.
    """
    dphi_col = _find_column(header_cols, "dphi", well)

    group_match = _GROUP_NUMBER_PATTERN.search(dphi_col)
    if group_match is None:
        raise ValueError(
            f"Could not determine the measurement group (Gr.<N>) from the "
            f"dphi column '{dphi_col}' for well '{well}'."
        )
    group_tag = f"Gr.{group_match.group(1)}"

    dt_col = _find_column(header_cols, "dt", group_tag)

    if optical_channels:
        optical_cols = []
        for channel in optical_channels:
            optical_cols.extend(_find_columns_all(header_cols, "Optical", group_tag, channel))
        # Preserve header order, drop duplicates (in case a channel string
        # matches more than one already-listed column).
        optical_cols = [c for i, c in enumerate(optical_cols) if c not in optical_cols[:i]]
    else:
        optical_cols = _find_columns_all(header_cols, "Optical", group_tag)

    dt_tag = _bracket_tag(dt_col)
    if dt_tag is None:
        raise ValueError(f"Could not determine measurement group for '{dt_col}'.")

    date_col = _find_column(header_cols, "Date", f"[{dt_tag}]")
    time_col = _find_column(header_cols, "Time", f"[{dt_tag}]")

    return {
        "dphi": dphi_col,
        "dt": dt_col,
        "optical_temperature": optical_cols,
        "date": date_col,
        "time": time_col,
    }


def _parse_experimental_data(lines, header_cols, columns):
    """
    Build a DataFrame containing only the columns of interest, from the
    first data line onward (first line in the file that does NOT start
    with '#').

    `columns['optical_temperature']` may list several raw column names;
    if so, they are parsed individually and then averaged row-wise into a
    single 'optical_temperature' column.
    """
    n_cols = len(header_cols)

    optical_raw_cols = columns["optical_temperature"]
    flat_col_map = {name: col for name, col in columns.items() if name != "optical_temperature"}
    for i, col in enumerate(optical_raw_cols):
        flat_col_map[f"_optical_{i}"] = col

    col_indices = {name: header_cols.index(col) for name, col in flat_col_map.items()}

    records = {name: [] for name in flat_col_map}
    in_data_section = False

    for raw_line in lines:
        line = raw_line.rstrip("\n")

        if not in_data_section:
            if line.startswith("#") or not line.strip():
                continue
            in_data_section = True

        if not line.strip():
            continue

        cells = line.split("\t")
        if len(cells) < n_cols:
            cells = cells + [""] * (n_cols - len(cells))

        for name, idx in col_indices.items():
            records[name].append(cells[idx].strip())

    df = pd.DataFrame(records)
    df = df[df["date"].str.strip() != ""].reset_index(drop=True)

    optical_keys = [f"_optical_{i}" for i in range(len(optical_raw_cols))]
    for key in optical_keys:
        df[key] = pd.to_numeric(df[key], errors="coerce")
    df["optical_temperature"] = df[optical_keys].mean(axis=1)
    df = df.drop(columns=optical_keys)

    return df


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_oxygen_data(directory, metadata_dict, well_mapping_file="data/well_mapping.csv"):
    """
    Process FirePlate O2 data for one well.

    Parameters
    ----------
    metadata_dict : dict
        - 'File name O2': name of the data file (e.g., "AE-772-1.txt")
        - 'output_folder': path to save results (optional, defaults to 'results')
        - 'Well': well name from overview.csv (e.g., "A1")
        - OPTICAL_TEMPERATURE_CHANNELS_KEY ("optical_temperature_channels"):
          optional list of channel identifiers (e.g. ["A2", "A4"]) to
          restrict which Optical Temp columns are averaged. If omitted,
          ALL Optical Temp channels found in the well's measurement group
          are averaged automatically.
    well_mapping_file : str
        Path to the well mapping CSV file (relative to current directory).
    """
    # === 1. Extract metadata ===
    file_name = metadata_dict["File name O2"]
    output_folder = metadata_dict.get("output_folder", "results")
    well = metadata_dict["Well"]

    data_dir = Path("data")
    file_O2 = data_dir / file_name

    output_dir = Path(output_folder)
    output_dir.mkdir(exist_ok=True)

    # === 2. Load Well Mapping ===
    mapping_path = Path(well_mapping_file)
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

    mapping_df = pd.read_csv(mapping_path)
    mapping_dict = dict(zip(mapping_df["experiment_well"], mapping_df["fireplate_well"]))

    if well not in mapping_dict:
        raise ValueError(f"Unknown well '{well}' in mapping file. Available: {list(mapping_dict.keys())}")

    fireplate_well = mapping_dict[well]
    print(f"Mapping: {well} -> {fireplate_well}")

    # === 3. Read raw file ===
    with open(file_O2, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # === 4. Calibration (read directly from the file) ===
    calibration = parse_calibration_section(lines, fireplate_well)

    # === 5. Locate the experimental data header and the columns we need ===
    header_line = None
    for line in lines:
        if not line.startswith("#"):
            header_line = line.rstrip("\n")
            break

    if header_line is None:
        raise RuntimeError("Could not find the experimental data header line in the file.")

    header_cols = [c.strip() for c in header_line.split("\t")]
    optical_channels = metadata_dict.get(OPTICAL_TEMPERATURE_CHANNELS_KEY)
    columns = find_experimental_columns(header_cols, fireplate_well, optical_channels=optical_channels)
    print(f"Optical temperature channel(s) used: {columns['optical_temperature']}")

    # === 6. Parse the experimental data rows ===
    df = _parse_experimental_data(lines, header_cols, columns)

    df.index = pd.to_datetime(df["date"] + " " + df["time"], dayfirst=True, errors="coerce")
    df.index.name = "date_time"

    for col in ("dt", "optical_temperature", "dphi"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # === 7. Recalculate O2 (pO2 -> µmol/L) ===
    temperature = df["optical_temperature"]
    salinity = 0.0

    pO2 = calculate_pO2_from_calibration(
        dphi=df["dphi"],
        temperature=temperature,
        calibration=calibration,
    )

    oxygen_uM = hPa_to_uM(
        data=pO2,
        temperature=temperature,
        salinity=salinity,
    )

    raw_data_dict = {
        fireplate_well: {
            "O2_time_s": df["dt"].to_numpy(),
            "O2_data": oxygen_uM.to_numpy(),
            "O2_temperature": temperature.to_numpy(),
        }
    }

    # === 8. Return only the essential data ===
    return raw_data_dict