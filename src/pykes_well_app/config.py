# --------------------------------------------------------------
# config.py
# --------------------------------------------------------------
"""Configuration for the simplified O₂‑liquid Streamlit app."""
# -----------------------------------------------------------------
# Imports – executed at import time
# -----------------------------------------------------------------
from pyKES.streamlit_app.config_interface import (
    PyKESStreamlitConfig,
    HomeConfig,
    DataUploadConfig,
    FileUploadHandler,
)
from pykes_well_app.data_parsing.general_processing_functions import (
    metadata_retrival_function,
    process_oxygen_data_liquid,
)
from pykes_well_app.data_parsing.raw_data_reading_function import (
    process_oxygen_data,
)
from pykes_well_app.parameters import (
    PROCESSING_PARAMETERS,
    GROUP_MAPPING,
    PLOTTING_INSTRUCTIONS,
)
# -----------------------------------------------------------------
# 1️⃣  File‑handler for O₂ (liquid phase)
# -----------------------------------------------------------------
file_handler_O2_liquid = FileUploadHandler(
    label="📊 O₂ (liquid phase) – Upload raw data",
    file_type=["csv", "txt"],
    help_text="Upload the O₂‑liquid measurement file (txt).",
    overview_df_experiment_column="Experiment",
    metadata_retrival_function=metadata_retrival_function,
    raw_data_reading_function=process_oxygen_data,
    processing_function=process_oxygen_data_liquid,
)
# -----------------------------------------------------------------
# 2️⃣  Data‑upload configuration (the heart of the UI)
# -----------------------------------------------------------------
DATA_UPLOAD_CONFIG = DataUploadConfig(
    file_handlers=[file_handler_O2_liquid],
    metadata_excel_experiment_column="Experiment",
    group_mapping=GROUP_MAPPING,
    plotting_instruction=PLOTTING_INSTRUCTIONS,
    processing_parameters=PROCESSING_PARAMETERS,
)
# -----------------------------------------------------------------
# 3️⃣  Home‑page configuration
# -----------------------------------------------------------------
HOME_CONFIG = HomeConfig(
    page_title="O₂‑Liquid Photocatalysis Analyzer",
    main_title="O₂‑Liquid Photocatalysis Analyzer",
    intro_markdown=(
        "Upload an *overview* Excel file that lists your experiments, "
        "then drag‑and‑drop the raw O₂‑liquid txt file. "
        "The app will read the data, apply the calibration you supplied, "
        "show O₂ concentration vs. time, and give you the kinetic parameters you need."
    ),
)
# -----------------------------------------------------------------
# 4️⃣  Top‑level Streamlit configuration
# -----------------------------------------------------------------
PYKES_CONFIG = PyKESStreamlitConfig(
    home_config=HOME_CONFIG,
    data_upload_config=DATA_UPLOAD_CONFIG,
    app_title="O₂‑Liquid Photocatalysis Analyzer",
    app_icon=":test_tube:",
)

__all__ = ["PYKES_CONFIG"]