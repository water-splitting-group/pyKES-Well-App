# parameters.py

# Parameters used during data processing
PROCESSING_PARAMETERS = {
    'O2_liquid_processing_parameters': {
        'offset': 60,           # seconds
        'savgol_window': 10,    # odd number, e.g., 5, 7, 9, 11
        'savgol_polyorder': 3,  # polynomial order
        'poly_order': 4,        # polynomial order for fit
    },
}

# Mapping of metadata columns to dataset groups (for visualisation)
GROUP_MAPPING = {
    'Reference': None,
    'Intensity': 'metadata/Irradiance [mW/cm2]',
    'Synthesis route': 'metadata/Synthesis route',
    'Flux temperature': 'metadata/Flux treatment temperature [°C]',
    'Co-catalyst loading': 'metadata/Co-catalyst A loading [wt%]',
    'Irradiation wavelength': 'metadata/Irradiation wavelength A [nm]',
    'Irradiance': 'metadata/Irradiance A [mW/cm2]',
    'Catalyst concentration': 'metadata/Catalyst concentration [mg/L]',
}

# Instruction for time series plotting and kinetic results
PLOTTING_INSTRUCTIONS = {
    'time_series_instructions': {
         'Raw (O2, liquid phase)': {
            'x': 'processed_data/O2_liquid_time_raw',
            'y': 'processed_data/O2_liquid_data_raw'   
        },
        'Reaction (O2, liquid phase)': {
            'x': 'processed_data/O2_liquid_time_reaction',
            'y': 'processed_data/O2_liquid_data_reaction'
        },
        'Poly fit (O2, liquid phase)': {
            'x': 'processed_data/O2_liquid_time_reaction',
            'y': 'processed_data/O2_liquid_poly_fit'
        },
        'Smoothed (O2, liquid phase)': {
            'x': 'processed_data/O2_liquid_time_reaction',
            'y': 'processed_data/O2_liquid_data_smoothed'
        },
        'Rate (O2, liquid phase)': {
            'x': 'processed_data/O2_liquid_time_diff',
            'y': 'processed_data/O2_liquid_data_diff'
        },
        'Rate poly fit (O2, liquid phase)': {
            'x': 'processed_data/O2_liquid_time_diff',
            'y': 'processed_data/O2_liquid_poly_fit_diff'
        },
    },
    'kinetic_results_instructions': {
        'Max rate (O2, liquid phase)': {
            'Value': 'processed_data/O2_liquid_max_rate',
            'Unit': 'Rate / µmol L⁻¹ s⁻¹'
        },
    },
}