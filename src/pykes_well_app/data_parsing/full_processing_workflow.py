"""The three pyKES ingestion stages for FirePlate oxygen measurements.

`read_in_single_experiment` calls the three functions below in turn, in its non-legacy
(overview-sheet driven) mode: the overview sheet names the logfile and the well, the
reader pulls that well's raw traces out of the logfile, and the processing stage
recalculates the dissolved oxygen from the raw phase angle.
"""

from pathlib import Path

import pandas as pd

from pyKES.utilities.unit_handler import Quantity
from pyKES.utilities.max_rate import extract_max_rate
from pyKES.utilities.offset_correction import offset_correction

from pykes_well_app.data_parsing.reprocessing_data import calculate_pO2_from_calibration, partial_pressure_to_micromolar, convert_umol_L_to_mol
from pykes_well_app.data_parsing.well_config import to_fireplate_well
from pykes_well_app.data_parsing.raw_data_reading_functions import (find_column, parse_fireplate_header,
                                                                    read_compensation_temperatures,
                                                                    read_measurement_table)
from pykes_well_app.parameters import PROCESSING_PARAMETERS

def find_conflicting_experiments(experiment_name: str, overview_df: pd.DataFrame) -> list[str]:
    """Find other experiments that read the same well out of the same logfile.

    A well can only be measured once per logfile, so two experiments sharing a
    ('File name O2', 'Well') pair would be handed byte-identical raw data under
    different names. In practice this means one of their 'File name O2' cells is a
    typo — the failure is otherwise silent, since every plate carries all 24 wells
    and the reader therefore succeeds.

    Parameters
    ----------
    experiment_name
        Experiment whose row is being read.
    overview_df
        Overview sheet holding one row per experiment.

    Returns
    -------
    list of str
        Names of the other experiments claiming the same well and logfile, sorted.
    """
    row = overview_df[overview_df['Experiment'] == experiment_name].iloc[0]

    same_well_and_file = (overview_df['File name O2'].eq(row['File name O2'])
                          & overview_df['Well'].eq(row['Well'])
                          & overview_df['Experiment'].ne(experiment_name))

    return sorted(overview_df.loc[same_well_and_file, 'Experiment'].astype(str))


def metadata_retrival_function(experiment_name: str, overview_df: pd.DataFrame) -> dict:
    """Collect the metadata of one experiment from the overview sheet.

    Parameters
    ----------
    experiment_name
        Value in the overview sheet's 'Experiment' column, e.g. ``'AE-852_A3'``.
    overview_df
        Overview sheet holding one row per experiment.

    Returns
    -------
    dict
        The sheet's row, plus `experiment_name`, `fireplate_well` and `raw_data_file`.
    """
    experiment_rows = overview_df[overview_df['Experiment'] == experiment_name]

    if len(experiment_rows) != 1:
        raise ValueError(f'Expected exactly one row for experiment "{experiment_name}", '
                         f'found {len(experiment_rows)}')

    metadata_dict = experiment_rows.iloc[0].to_dict()
    metadata_dict['experiment_name'] = experiment_name
    metadata_dict['fireplate_well'] = to_fireplate_well(metadata_dict['Well'])
    metadata_dict['raw_data_file'] = metadata_dict['File name O2']

    # Both members of a conflicting pair fail: the sheet alone cannot say which of
    # the two 'File name O2' cells is the wrong one.
    conflicts = find_conflicting_experiments(experiment_name, overview_df)

    if conflicts:
        raise ValueError(f'{experiment_name} reads well {metadata_dict["Well"]} '
                         f'(FirePlate {metadata_dict["fireplate_well"]}) from '
                         f'{metadata_dict["raw_data_file"]}, but {", ".join(conflicts)} '
                         f'already claims that well in that file. One of their '
                         f'"File name O2" entries in the overview sheet is wrong.')

    return metadata_dict

def raw_data_reading_function(directory: Path, metadata_dict: dict) -> dict:
    """Read the raw traces of one well from its FirePlate logfile.

    Parameters
    ----------
    directory
        Directory holding the logfile named by `metadata_dict['raw_data_file']`.
    metadata_dict
        Metadata of the experiment, as returned by the metadata retrieval function. Uses
        `raw_data_file` and `fireplate_well`.

    Returns
    -------
    dict
        Keys `time_s`, `dphi`, `compensation_temperatures` (one row per optical
        temperature sensor on the plate), `compensation_temperature_wells` (row index ->
        well name), `oxygen_umol_L` (the Workbench's own result, kept for comparison) and
        `calibration`.
    """
    path = Path(directory) / metadata_dict['raw_data_file']
    header = parse_fireplate_header(path)
    well = metadata_dict['fireplate_well']

    if well not in header['well_labels']:
        raise ValueError(f'Well {well} carries no oxygen sensor in {path.name}; '
                         f'calibrated wells are {sorted(header["well_labels"])}')

    data = read_measurement_table(path, header)
    columns = list(data.columns)
    group_tag = header['group_tag']
    well_label = header['well_labels'][well]

    compensation_temperatures, compensation_temperature_wells = read_compensation_temperatures(data, header)

    return {
        'time_s': data[find_column(columns, 'dt (s)', f'{group_tag} Main')].to_numpy(),
        'dphi': data[find_column(columns, 'dphi (', f'{group_tag}.{well_label} Main')].to_numpy(),
        'compensation_temperatures': compensation_temperatures,
        'compensation_temperature_wells': compensation_temperature_wells,
        'oxygen_umol_L': data[find_column(columns, 'Oxygen (', f'{group_tag}.{well_label} Main')].to_numpy(),
        'calibration': {
            **header['calibration'][well],
            'salinity': float(header['settings']['Salinity (g/l)']),
            'sensor_code': header['sensor_code'],
        },
    }

def processing_function(raw_data_dict: dict, metadata_dict: dict) -> dict:
    """Recalculate dissolved oxygen for one experiment from its raw traces.

    Parameters
    ----------
    raw_data_dict
        Raw data as returned by `raw_data_reading_function`.
    metadata_dict
        Metadata of the experiment. Unused, present for the pyKES processing interface.

    Returns
    -------
    dict
        Keys `time_s`, `pO2_hPa` and `oxygen_umol_L`.
    """
    calibration = raw_data_dict['calibration']

    # The plate's optical temperature sensors sit in different wells and read slightly
    # differently; their average is the best estimate of the plate temperature.
    temperature = raw_data_dict['compensation_temperatures'].mean(axis=0)

    partial_pressure = calculate_pO2_from_calibration(raw_data_dict['dphi'], temperature, calibration)
    oxygen_umol_L = partial_pressure_to_micromolar(partial_pressure, temperature, calibration['salinity'])

    oxygen_mol = convert_umol_L_to_mol(oxygen_umol_L, metadata_dict['Liquid phase volume [mL]'])

    if 'Offset' in metadata_dict:
        offset = Quantity(metadata_dict['Offset'], 's')
    else:
        offset = Quantity(PROCESSING_PARAMETERS['O2_liquid_processing_parameters']['offset'], 's')

    time_reaction, data_reaction = offset_correction(raw_data_dict['time_s'], 
                                                     oxygen_mol.unit['mol'], 
                                                     offset.unit['s'],
                                                     metadata_dict['Pyroscience Irradiation start [s]'],
                                                     metadata_dict['Pyroscience Irradiation end [s]'])

    time_reaction_quantity = Quantity(time_reaction, 's')
    data_reaction_quantity = Quantity(data_reaction, 'mol')

    result = extract_max_rate(time_reaction_quantity, 
                              data_reaction_quantity)

    processed_data_dict = {'pO2_hPa': partial_pressure,
                           'oxygen_umol_L': oxygen_umol_L,
                           'time_reaction_s': time_reaction_quantity.unit['s'],
                           'time_unit': 's',
                           'data_reaction_umol': data_reaction_quantity.unit['umol'],
                           'data_unit': 'umol',
                           'smoothed_gaussian_umol': result.smooth.unit['umol'],
                           'smoothed_gaussian_unit': 'umol',
                           'rate_gaussian_umol_s': result.rate.unit['umol/s'],
                           'rate_gaussian_unit': 'umol/s',
                           'max_rate_umol_s': result.max_rate.unit['umol/s'],
                           'max_rate_unit': 'umol/s',
                           'max_rate_crosscheck_umol_s': result.max_rate_crosscheck.unit['umol/s'],
                           'max_rate_crosscheck_unit': 'umol/s',
                           'max_rate_time_s': result.t_max_rate.unit['s'],
                           'max_rate_time_unit': 's',
                           }

    return processed_data_dict


def test_function():
    """Run the full workflow for one well of AE-852-1.txt and check it against the logfile."""
    import numpy as np

    from pykes_well_app.data_parsing.reprocessing_data import reproduce_workbench_oxygen

    directory = Path(__file__).resolve().parents[3] / 'data' / 'Validation'
    overview_df = pd.read_excel(directory / '260820_validation.xlsx')

    metadata_dict = metadata_retrival_function('AE-852_C2', overview_df)
    raw_data_dict = raw_data_reading_function(directory, metadata_dict)
    processed_data_dict = processing_function(raw_data_dict, metadata_dict)

    import pprint as pp
    pp.pprint(raw_data_dict)

    # print(f'experiment  : {metadata_dict["experiment_name"]}')
    # print(f'well        : {metadata_dict["Well"]} -> {metadata_dict["fireplate_well"]}')
    # print(f'logfile     : {metadata_dict["raw_data_file"]}')
    # print(f'calibration : {raw_data_dict["calibration"]}')
    # print(f'points      : {len(raw_data_dict["time_s"])}\n')

    # The parsing and the sensor model are correct if feeding the Workbench's own 0 C
    # compensation temperature back in returns the Workbench's own oxygen column.
    deviation = np.abs(reproduce_workbench_oxygen(raw_data_dict) - raw_data_dict['oxygen_umol_L'])
    # print(f'reproducing the logged column at 0 C: max deviation {deviation.max():.2e} umol/L\n')

    comparison = pd.DataFrame({
        'time_s': raw_data_dict['time_s'],
        'dphi': raw_data_dict['dphi'],
        'temperature': raw_data_dict['compensation_temperatures'].mean(axis=0),
        'pO2_hPa': processed_data_dict['pO2_hPa'],
        'reprocessed_umol_L': processed_data_dict['oxygen_umol_L'],
        'logged_umol_L': raw_data_dict['oxygen_umol_L'],
    })
    # print(comparison.iloc[::200].to_string(index=False))

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()

    ax2 = ax.twinx()



    ax.plot(processed_data_dict['time_reaction_s'], processed_data_dict['data_reaction_umol'], '.', label='reprocessed cumulative')
    ax.plot(processed_data_dict['time_reaction_s'], processed_data_dict['smoothed_gaussian_umol'], label='smoothed cumulative')

    ax2.plot(processed_data_dict['time_reaction_s'], processed_data_dict['rate_gaussian_umol_s'], label='reprocessed', alpha = 0.5)
    ax2.plot(processed_data_dict['max_rate_time_s'], processed_data_dict['max_rate_umol_s'], 'ro', label='max rate')

    plt.show()

if __name__ == '__main__':
    test_function()
