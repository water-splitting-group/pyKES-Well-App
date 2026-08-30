"""Reading of PyroScience FirePlate Workbench logfiles for a single well.

A Workbench logfile holds one measurement of a whole plate: a '#'-prefixed header with
the sensor settings and the per-well calibration, followed by one wide tab-separated
table with a block of columns per well. These functions pull out the header, the
calibration of one well and that well's raw traces.

Workbench versions differ in how they label wells: 1.5.7 names them by row and column
('A4'), older versions number them continuously ('4'). Wells are keyed by the row/column
name throughout, with the logfile's own label kept alongside because the measurement-table
column tags are built from it.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

from pykes_well_app.data_parsing.well_config import well_name_from_number

# Encoding written by the Workbench on Windows.
LOGFILE_ENCODING = 'latin-1'

# Header lines identifying the oxygen channel and the optical temperature sensors that
# compensate it. The leading '#' is stripped before matching.
OXYGEN_GROUP_PATTERN = re.compile(r'Group \[(\w+ Gr\.\d+)\] - Oxygen Sensor - (\S+) - Well numbers: (.*)')
COMPENSATION_GROUP_PATTERN = re.compile(r'Compensation Group \[\w+ Gr\.\d+\].*Well numbers: (.*)')

# A well label written by an older Workbench, i.e. a continuous well number rather than
# a row letter followed by a column number.
NUMERIC_WELL_LABEL_PATTERN = re.compile(r'^\d+$')

# Offsets of the settings and calibration lines relative to the channel's 'Group [...]' line.
SETTINGS_NAMES_OFFSET = 2
SETTINGS_VALUES_OFFSET = 3
CALIBRATION_NAMES_OFFSET = 4
CALIBRATION_FIRST_WELL_OFFSET = 5

# Workbench calibration column -> name used by the oxygen model in reprocessing_data.
CALIBRATION_FIELDS = {
    'dphi 100% (\N{DEGREE SIGN})': 'dphi100',
    'dphi 0% (\N{DEGREE SIGN})': 'dphi0',
    'f': 'f',
    'm': 'm',
    'F(Hz)': 'freq',
    'tt(%/K)': 'tt',
    'kt(%/K)': 'kt',
    'mt(1/K)': 'mt',
    'Air Pressure (mbar)': 'pressure',
    'Temperature (\N{DEGREE SIGN}C)': 'temp100',
    'Humidity (%RH)': 'humidity',
    'Temperature (\N{DEGREE SIGN}C) at 0%': 'temp0',
    'Partial Volume of Oxygen (%O2)': 'percentO2',
}

# Sensor constants the Workbench reports in %/K but the oxygen model expects in 1/K.
PERCENT_PER_KELVIN_FIELDS = ('tt', 'kt')


def read_header_lines(path: Path) -> list[str]:
    """Read the '#'-prefixed header block of a Workbench logfile.

    Parameters
    ----------
    path
        Path of the logfile.

    Returns
    -------
    list of str
        Header lines without their '#' prefix and trailing padding tabs. Their count is
        also the number of rows to skip before the measurement table.
    """
    lines = []
    with open(path, encoding=LOGFILE_ENCODING) as logfile:
        for line in logfile:
            if not line.startswith('#'):
                break
            lines.append(line[1:].rstrip())

    return lines


def find_header_line(header_lines: list[str], pattern: re.Pattern) -> tuple[int, re.Match]:
    """Locate the single header line matching a pattern.

    Parameters
    ----------
    header_lines
        Header block as returned by `read_header_lines`.
    pattern
        Pattern to search for.

    Returns
    -------
    tuple
        Index of the matching line and the match object.
    """
    matches = [(index, pattern.match(line)) for index, line in enumerate(header_lines) if pattern.match(line)]

    if len(matches) != 1:
        raise ValueError(f'Expected exactly one header line matching "{pattern.pattern}", found {len(matches)}')

    return matches[0]


def parse_settings(names_line: str, values_line: str) -> dict:
    """Parse a 'Settings:' header line pair into a name -> value dictionary.

    Parameters
    ----------
    names_line
        Line starting with 'Settings:' listing the setting names.
    values_line
        Following line holding the values.

    Returns
    -------
    dict
        Raw settings as written by the Workbench, values left as strings.
    """
    return dict(zip(names_line.split('\t')[1:], values_line.split('\t')[1:]))


def parse_calibration(names_line: str, values_line: str) -> dict:
    """Parse one well's oxygen calibration row.

    Parameters
    ----------
    names_line
        Line starting with 'Calibration:' listing the calibration column names.
    values_line
        The well's calibration row.

    Returns
    -------
    dict
        Calibration in the units expected by the oxygen model, i.e. sensor constants
        `tt` and `kt` converted from %/K to 1/K.
    """
    calibration = {}
    for name, value in zip(names_line.split('\t')[1:], values_line.split('\t')[1:]):
        if name not in CALIBRATION_FIELDS:
            continue

        field = CALIBRATION_FIELDS[name]
        calibration[field] = float(value) / 100 if field in PERCENT_PER_KELVIN_FIELDS else float(value)

    missing = set(CALIBRATION_FIELDS.values()) - set(calibration)
    if missing:
        raise ValueError(f'Calibration is missing the fields {sorted(missing)}')

    return calibration


def parse_well_labels(well_numbers: str) -> dict[str, str]:
    """Map the wells of a channel to the labels the logfile writes for them.

    Parameters
    ----------
    well_numbers
        Comma-separated well list from a 'Well numbers:' header line, in either the
        row/column form ('A4, A6') or the continuous form ('4, 6').

    Returns
    -------
    dict
        Row/column well name -> label as written in the logfile, in header order. The
        label is what the measurement-table column tags are built from.
    """
    labels = [label.strip() for label in well_numbers.split(',')]

    return {well_name_from_number(int(label)) if NUMERIC_WELL_LABEL_PATTERN.match(label) else label: label
            for label in labels}


def parse_fireplate_header(path: Path) -> dict:
    """Parse the header of a FirePlate logfile into settings and per-well calibrations.

    Parameters
    ----------
    path
        Path of the logfile.

    Returns
    -------
    dict
        Keys `group_tag` (the oxygen channel's column tag, e.g. 'A Gr.2'), `sensor_code`,
        `settings`, `calibration` (per FirePlate well), `well_labels` and
        `compensation_well_labels` (well name -> logfile label, for the oxygen and the
        optical temperature wells) and `n_header_lines`.
    """
    header_lines = read_header_lines(path)

    group_index, group_match = find_header_line(header_lines, OXYGEN_GROUP_PATTERN)
    group_tag, sensor_code, well_numbers = group_match.groups()
    well_labels = parse_well_labels(well_numbers)

    calibration_names = header_lines[group_index + CALIBRATION_NAMES_OFFSET]
    calibration = {
        well: parse_calibration(calibration_names, header_lines[group_index + CALIBRATION_FIRST_WELL_OFFSET + offset])
        for offset, well in enumerate(well_labels)
    }

    _, compensation_match = find_header_line(header_lines, COMPENSATION_GROUP_PATTERN)

    return {
        'group_tag': group_tag,
        'sensor_code': sensor_code,
        'settings': parse_settings(header_lines[group_index + SETTINGS_NAMES_OFFSET],
                                   header_lines[group_index + SETTINGS_VALUES_OFFSET]),
        'calibration': calibration,
        'well_labels': well_labels,
        'compensation_well_labels': parse_well_labels(compensation_match.group(1)),
        'n_header_lines': len(header_lines),
    }


def find_column(columns: list[str], prefix: str, tag: str) -> str:
    """Find the measurement-table column with a given quantity and channel tag.

    Column names look like ``'dphi (°) [A Gr.2.A4 Main]'``; the quantity is matched by
    prefix because its unit varies between logfiles (e.g. µmol/L vs %O2).

    Parameters
    ----------
    columns
        Column names of the measurement table.
    prefix
        Start of the quantity name, e.g. ``'Oxygen ('``.
    tag
        Channel tag inside the brackets, e.g. ``'A Gr.2.A4 Main'``.

    Returns
    -------
    str
        The matching column name.
    """
    matches = [column for column in columns
               if column.strip().startswith(prefix) and column.endswith(f'[{tag}]')]

    if len(matches) != 1:
        raise ValueError(f'Expected exactly one "{prefix}" column for tag "{tag}", found {matches}')

    return matches[0]


def read_measurement_table(path: Path, header: dict) -> pd.DataFrame:
    """Read the measurement table that follows a logfile's header block.

    Parameters
    ----------
    path
        Path of the logfile.
    header
        Parsed header, as returned by `parse_fireplate_header`.

    Returns
    -------
    pandas.DataFrame
        The wide measurement table, one block of columns per well.
    """
    return pd.read_csv(path, skiprows=header['n_header_lines'], sep='\t', encoding=LOGFILE_ENCODING)


def read_compensation_temperatures(data: pd.DataFrame, header: dict) -> tuple[np.ndarray, dict[int, str]]:
    """Read every optical temperature trace that compensates the oxygen channel.

    Parameters
    ----------
    data
        Measurement table, as returned by `read_measurement_table`.
    header
        Parsed header, as returned by `parse_fireplate_header`.

    Returns
    -------
    tuple
        2D array of temperatures in degrees Celsius with one compensation well per row
        and one time point per column, and a dict mapping each row index to its well name.
    """
    columns = list(data.columns)
    group_tag = header['group_tag']

    temperatures = [data[find_column(columns, 'Optical Temp. (', f'{group_tag}.{label} CompT')].to_numpy()
                    for label in header['compensation_well_labels'].values()]

    return np.vstack(temperatures), dict(enumerate(header['compensation_well_labels']))
