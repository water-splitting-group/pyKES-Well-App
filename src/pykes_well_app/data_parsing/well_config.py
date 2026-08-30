"""Mapping between experiment well names and physical FirePlate well positions.

The 24 experiment wells (rows A-D, columns 1-6) sit on every other position of the
96-well FirePlate (rows A, C, E, G and even columns), so the well name used in the
overview sheet is never the well name used in the Workbench logfile.
"""

# Physical layout of the FirePlate.
PLATE_ROWS = 8
PLATE_COLUMNS = 12

# Experiment well name (24-well plate) -> FirePlate well name (96-well plate).
# Mirrors data/well_mapping.csv; kept here so the mapping is not re-read per experiment.
EXPERIMENT_TO_FIREPLATE_WELL = {
    'A1': 'A2',  'A2': 'A4',  'A3': 'A6',  'A4': 'A8',  'A5': 'A10', 'A6': 'A12',
    'B1': 'C2',  'B2': 'C4',  'B3': 'C6',  'B4': 'C8',  'B5': 'C10', 'B6': 'C12',
    'C1': 'E2',  'C2': 'E4',  'C3': 'E6',  'C4': 'E8',  'C5': 'E10', 'C6': 'E12',
    'D1': 'G2',  'D2': 'G4',  'D3': 'G6',  'D4': 'G8',  'D5': 'G10', 'D6': 'G12',
}


def to_fireplate_well(experiment_well: str) -> str:
    """Translate an experiment well name into the FirePlate well name.

    Parameters
    ----------
    experiment_well
        Well name as used in the overview sheet, e.g. ``'B3'``.

    Returns
    -------
    str
        Well name as used in the Workbench logfile, e.g. ``'C6'``.
    """
    if experiment_well not in EXPERIMENT_TO_FIREPLATE_WELL:
        raise KeyError(f'Unknown experiment well "{experiment_well}", expected one of '
                       f'{sorted(EXPERIMENT_TO_FIREPLATE_WELL)}')

    return EXPERIMENT_TO_FIREPLATE_WELL[experiment_well]


def well_name_from_number(well_number: int) -> str:
    """Translate a continuously numbered FirePlate well into its row/column name.

    Workbench versions before 1.5.7 number the 96 wells continuously and row by row
    (1 -> 'A1', 13 -> 'B1') instead of naming them by row letter and column number.

    Parameters
    ----------
    well_number
        One-based well number, counted row by row.

    Returns
    -------
    str
        Well name such as ``'E8'``.
    """
    if not 1 <= well_number <= PLATE_ROWS * PLATE_COLUMNS:
        raise ValueError(f'Well number {well_number} is outside a '
                         f'{PLATE_ROWS * PLATE_COLUMNS}-well plate')

    row, column = divmod(well_number - 1, PLATE_COLUMNS)

    return f'{chr(ord("A") + row)}{column + 1}'


def well_position(fireplate_well: str) -> tuple[int, int]:
    """Return the (row, column) plate coordinates of a FirePlate well.

    Parameters
    ----------
    fireplate_well
        Well name such as ``'E10'``.

    Returns
    -------
    tuple of int
        Zero-based row index and one-based column number.
    """
    return ord(fireplate_well[0]) - ord('A'), int(fireplate_well[1:])


def nearest_well(fireplate_well: str, candidates: list[str]) -> str:
    """Pick the candidate well physically closest to a given well.

    A FirePlate carries several optical temperature sensors; the one nearest to the
    oxygen well is the best estimate of that well's temperature.

    Parameters
    ----------
    fireplate_well
        Well whose neighbour is sought.
    candidates
        Well names to choose from.

    Returns
    -------
    str
        The closest candidate well name.
    """
    row, column = well_position(fireplate_well)

    def squared_distance(candidate: str) -> float:
        candidate_row, candidate_column = well_position(candidate)
        return (candidate_row - row) ** 2 + (candidate_column - column) ** 2

    return min(candidates, key=squared_distance)
