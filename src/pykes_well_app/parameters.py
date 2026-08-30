# Parameters used during data processing
PROCESSING_PARAMETERS = {
    'O2_liquid_processing_parameters': { 
                        'offset': 60,
                    },
}

# Mapping of metadata columns to dataset groups (for visualisation)
GROUP_MAPPING = {
        'Reference': None,
        }

# Instruction for time series plotting (mapping of plot labels to dataset paths)
# and kinetic results plotting (mapping of result labels to dataset paths and units)

PLOTTING_INSTRUCTIONS = {
    'time_series_instructions': {
                    'Raw (O2, liquid phase) - wrong temperature compensation': {
                        'x': 'raw_data/time_s',
                        'y': 'raw_data/oxygen_umol_L'
                        },
                    'Raw (O2, liquid phase) - reprocessed': {
                        'x': 'raw_data/time_s',
                        'y': 'processed_data/oxygen_umol_L'
                        },
                    'Reaction (O2, liquid phase)': {
                        'x': 'processed_data/time_reaction_s',
                        'y': 'processed_data/data_reaction_umol',
                        'unit_x': 'processed_data/time_unit',
                        'unit_y': 'processed_data/data_unit',
                        },
                    'Smoothed (O2, liquid phase)': {
                        'x': 'processed_data/time_reaction_s',
                        'y': 'processed_data/smoothed_gaussian_umol',
                        'unit_x': 'processed_data/time_unit',
                        'unit_y': 'processed_data/smoothed_gaussian_unit',
                        },
                    'Rate (O2, liquid phase)': {
                        'x': 'processed_data/time_reaction_s',
                        'y': 'processed_data/rate_gaussian_umol_s',
                        'x_point': 'processed_data/max_rate_time_s',
                        'y_point': 'processed_data/max_rate_umol_s',
                        'unit_x': 'processed_data/time_unit',
                        'unit_y': 'processed_data/rate_gaussian_unit',
                        },
                },
    
    'kinetic_results_instructions': {
        'Max rate (O2, liquid phase)': {'Value': 'processed_data/max_rate_umol_s',
                                        'Unit': 'Rate / umol/s'},
    },

    'results_table_instructions': {
        'Max. rate (umol/s)': {'result': 'processed_data/max_rate_umol_s'},
        'Max. rate crosscheck (umol/s)': {'result': 'processed_data/max_rate_crosscheck_umol_s',
                                          'format': '.10f'},
    },
}
