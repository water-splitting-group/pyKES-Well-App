from pyKES.streamlit_app.components import render_data_upload
from pykes_well_app.config import PYKES_CONFIG

# Render the data upload component with configuration from config.py
render_data_upload(PYKES_CONFIG.data_upload_config)
