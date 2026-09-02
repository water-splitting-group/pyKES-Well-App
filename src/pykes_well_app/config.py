from pyKES.streamlit_app.config_interface import (
    PyKESStreamlitConfig,
    HomeConfig,
    DataUploadConfig,
    FileUploadHandler,
)

from pyKES.utilities.version_information import get_git_commit

from pykes_well_app.data_parsing.full_processing_workflow import (
    metadata_retrival_function,
    raw_data_reading_function,
    processing_function
)

from pykes_well_app.parameters import (
    PROCESSING_PARAMETERS,
    GROUP_MAPPING,
    PLOTTING_INSTRUCTIONS,
)

# -----------------------------------------------------------------------------
# Provenance of this app, stored in every dataset it processes
# -----------------------------------------------------------------------------

# Recorded in dataset.version['external_version'], so the processed data can be
# traced back to the code that produced it. get_git_commit returns None outside
# a git work tree (e.g. a deployment from a source archive).
EXTERNAL_VERSION = {
    "app": "pyKES-Well-App",
    "commit": get_git_commit(__file__),
}

# -----------------------------------------------------------------------------
# File Handler Config
# -----------------------------------------------------------------------------

file_handler_O2_well_plate =  FileUploadHandler(
                            label = "📊 O2 (well plate) - Upload Raw Data",
                            file_type = ["csv", "txt"],
                            help_text = "Upload O2 well plate liquid phase measurement raw data files (CSV or TXT).",
                            overview_df_experiment_column = "Experiment",
                            metadata_retrival_function = metadata_retrival_function,
                            raw_data_reading_function = raw_data_reading_function,
                            processing_function = processing_function,
                            )

# -----------------------------------------------------------------------------
# Data Upload and Home Configuration
# -----------------------------------------------------------------------------

DATA_UPLOAD_CONFIG = DataUploadConfig(
    file_handlers = [file_handler_O2_well_plate],
    metadata_excel_experiment_column="Experiment",
    group_mapping=GROUP_MAPPING,
    plotting_instruction=PLOTTING_INSTRUCTIONS,
    processing_parameters=PROCESSING_PARAMETERS,
    external_version=EXTERNAL_VERSION,
)

HOME_CONFIG = HomeConfig(
    page_title = "pyKES HTE Well Plate Analysis",
    main_title = "pyKES HTE Well Plate Analysis",
)

# -----------------------------------------------------------------------------
# Top-level app configuration
# -----------------------------------------------------------------------------

PYKES_CONFIG = PyKESStreamlitConfig(
    home_config = HOME_CONFIG,
    data_upload_config = DATA_UPLOAD_CONFIG,
    app_title = "Photocatalysis Data Analysis System",
    app_icon = ":test_tube:",
)



