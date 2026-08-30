import numpy as np
import pandas as pd
from pathlib import Path

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


def raw_data_reading_function(directory: Path, 
                              metadata_dict: dict):
    
    file = directory / metadata_dict['File name O2']

    with open(file, encoding='ISO8859') as data_file:
        lines = data_file.readlines()

    # The file starts with ~25 lines of instrument metadata prefixed by '#';
    # the measurement table begins at the line starting with 'Date'.
    header_index = next(i for i, line in enumerate(lines) if line.startswith('Date'))
    table = pd.read_csv(io.StringIO(''.join(lines[header_index:])), sep='\t')

    # Column labels carry the channel in brackets, so match on the stable parts of the name
    time_column = next(column for column in table.columns if 'dt (s)' in column and 'Main' in column)
    value_column = next(column for column in table.columns if 'Oxygen' in column and 'Main' in column)

    raw_data_dict = {
        'O2_time_s': table[time_column].to_numpy(float),
        'O2_data': table[value_column].to_numpy(float),
    }

    return raw_data_dict


def testing():
    import pprint as pp

    overview_df = pd.read_excel('/Users/jacob/Downloads/260820_validation.xlsx')

    metadata_dict = metadata_retrival_function('AE-852_A3', overview_df)
    raw_data = raw_data_reading_function(Path('/Users/jacob/Downloads'), metadata_dict)



if __name__ == "__main__":
    testing()