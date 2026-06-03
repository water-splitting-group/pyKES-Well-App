import numpy as np
from pathlib import Path
from pykes_well_app.parameters import PROCESSING_PARAMETERS
from scipy.signal import savgol_filter
from pyKES.utilities.find_nearest import find_nearest
from pyKES.utilities.time_series_resampling import resample_time_series
from pyKES.utilities.offset_correction import offset_correction

def metadata_retrival_function(experiment_name: str, 
                               overview_df):
    '''
    Given an experiment name and an overview DataFrame, retrieves the metadata for the specified experiment.
    Returns a dictionary containing the metadata.
    '''

    experiment_row = overview_df[overview_df['Experiment'] == experiment_name]
    
    if experiment_row.empty:
        raise ValueError(f"No experiment found with name: {experiment_name}")
    
    if len(experiment_row) > 1:
        raise ValueError(f"Multiple experiments found with name: {experiment_name}")
    
    metadata_dict = experiment_row.iloc[0].to_dict()
    metadata_dict['experiment_name'] = metadata_dict['Experiment']

    return metadata_dict

## Making lru_cached file reading function for repeated reads (since each experiment reads the same file)


def raw_data_data_reading_function(directory: Path, 
                                   metadata_dict: dict):
    
    pass

def processing_data(time: np.ndarray,
                    data: np.ndarray,
                    start: float,
                    end: float,
                    prefix: str,
                    offset: float,
                    savgol_window: int,
                    savgol_polyorder: int,
                    poly_order: int,
                    ):
    time_reaction, data_reaction = offset_correction(time, data, offset, start, end)

    # Remove NaN values before smoothing
    mask = np.isfinite(data_reaction) & np.isfinite(time_reaction)
    time_reaction = time_reaction[mask]
    data_reaction = data_reaction[mask]

    data_smoothed = savgol_filter(data_reaction, savgol_window, savgol_polyorder)
    data_diff = np.diff(data_smoothed) / np.diff(time_reaction)
    time_diff = time_reaction[1:]

    coeffs = np.polyfit(time_reaction, data_reaction, poly_order)
    data_poly_fit = np.polyval(coeffs, time_reaction)

    poly_fit_diff = np.diff(data_poly_fit) / np.diff(time_reaction)
    max_rate = np.max(poly_fit_diff)

    processed_data = {
        f'{prefix}_time_reaction': time_reaction,
        f'{prefix}_data_reaction': data_reaction,
        f'{prefix}_data_smoothed': data_smoothed,
        f'{prefix}_data_diff': data_diff,
        f'{prefix}_time_diff': time_diff,
        f'{prefix}_poly_fit': data_poly_fit,
        f'{prefix}_poly_fit_diff': poly_fit_diff,
        f'{prefix}_max_rate': max_rate,
    }

    return processed_data

def process_oxygen_data_liquid(raw_data_dict, metadata_dict):
    """
    Processing function for O2 liquid phase data.
    Called by pyKES after raw data reading.
    """
    fireplate_well = list(raw_data_dict.keys())[0]
    time = raw_data_dict[fireplate_well]['O2_time_s']
    data = raw_data_dict[fireplate_well]['O2_data']
    ...

    # Get processing parameters
    params = PROCESSING_PARAMETERS['O2_liquid_processing_parameters']

    # Get reaction window from metadata
    start = metadata_dict['Pyroscience Irradiation start [s]']
    end = metadata_dict['Pyroscience Irradiation end [s]']

    processed_data = processing_data(
        time=time,
        data=data,
        start=start,
        end=end,
        prefix='O2_liquid',
        offset=params['offset'],
        savgol_window=params['savgol_window'],
        savgol_polyorder=params['savgol_polyorder'],
        poly_order=params['poly_order'],
    )

    return processed_data

def testing():
    pass

if __name__ == "__main__":
    testing()