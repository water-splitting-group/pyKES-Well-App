import numpy as np
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

## Making lru_cached file reading function for repeated reads (since each experiment reads the same file)


def raw_data_data_reading_function(directory: Path, 
                                   metadata_dict: dict):
    
    pass



def testing():
    pass

if __name__ == "__main__":
    testing()