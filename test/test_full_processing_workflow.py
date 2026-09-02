"""Tests for the overview-sheet stage of the FirePlate ingestion workflow.

All frames here are synthetic, so the expected metadata is known by construction and
the tests do not depend on any measurement file being present locally.
"""

import pandas as pd
import pytest

from pykes_well_app.data_parsing.full_processing_workflow import (
    find_conflicting_experiments,
    metadata_retrival_function,
)


def build_overview_df(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    """Build a minimal overview sheet from (experiment, well, logfile) triples.

    Parameters
    ----------
    rows
        One triple per experiment, matching the sheet's 'Experiment', 'Well' and
        'File name O2' columns.

    Returns
    -------
    pd.DataFrame
        Overview sheet carrying only the columns the metadata stage reads.
    """
    return pd.DataFrame(rows, columns=['Experiment', 'Well', 'File name O2'])


# A clean sheet: two wells off one plate, one well off another.
CLEAN_ROWS = [
    ('AE-852_B1', 'B1', 'AE-852-1.txt'),
    ('AE-852_A5', 'A5', 'AE-852-1.txt'),
    ('AE-853_B1', 'B1', 'AE-853-1.txt'),
]

# The historical defect: AE-853_B1 points at AE-852's logfile, so both rows resolve
# to well C2 of AE-852-1.txt and would store identical raw data under two names.
CONFLICTING_ROWS = [
    ('AE-852_B1', 'B1', 'AE-852-1.txt'),
    ('AE-853_B1', 'B1', 'AE-852-1.txt'),
]


def test_metadata_resolves_well_and_logfile():
    metadata = metadata_retrival_function('AE-852_B1', build_overview_df(CLEAN_ROWS))

    assert metadata['experiment_name'] == 'AE-852_B1'
    assert metadata['raw_data_file'] == 'AE-852-1.txt'
    # B1 on the 24-well plate is C2 on the 96-well FirePlate.
    assert metadata['fireplate_well'] == 'C2'


def test_same_well_on_different_plates_is_not_a_conflict():
    overview_df = build_overview_df(CLEAN_ROWS)

    assert find_conflicting_experiments('AE-853_B1', overview_df) == []
    assert metadata_retrival_function('AE-853_B1', overview_df)['raw_data_file'] == 'AE-853-1.txt'


def test_duplicate_well_and_logfile_is_rejected():
    overview_df = build_overview_df(CONFLICTING_ROWS)

    with pytest.raises(ValueError, match='AE-852_B1'):
        metadata_retrival_function('AE-853_B1', overview_df)


def test_both_members_of_a_conflicting_pair_are_rejected():
    overview_df = build_overview_df(CONFLICTING_ROWS)

    # Neither row can be trusted, so ingesting either must fail rather than silently
    # picking one of them.
    assert find_conflicting_experiments('AE-852_B1', overview_df) == ['AE-853_B1']
    assert find_conflicting_experiments('AE-853_B1', overview_df) == ['AE-852_B1']


def test_unknown_experiment_is_rejected():
    with pytest.raises(ValueError, match='found 0'):
        metadata_retrival_function('AE-999_A1', build_overview_df(CLEAN_ROWS))


def test_duplicate_experiment_name_is_rejected():
    overview_df = build_overview_df(CLEAN_ROWS + [('AE-852_B1', 'B1', 'AE-852-1.txt')])

    with pytest.raises(ValueError, match='found 2'):
        metadata_retrival_function('AE-852_B1', overview_df)
