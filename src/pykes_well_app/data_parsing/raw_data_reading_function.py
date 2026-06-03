"""
Adapted FirePlate Oxygen Recalculation Script (Dynamic Column Parsing)
======================================================================
Uses metadata_dict to get file path and calibration.
Dynamically parses column names from the header line.
Supports variable numbers of wells and channels.
"""

from pathlib import Path
import pandas as pd
from io import StringIO
from pyrotoolbox.oxygen import calculate_pO2_from_calibration, hPa_to_uM
import re


def load_calibration_from_file(filepath):
    """
    Load calibration values from a CSV file.
    File format:
        parameter,C02,E02,G02
        dphi0,50.563,50.453,50.633
        ...
    """
    if not Path(filepath).exists():
        raise FileNotFoundError(f"Calibration file not found: {filepath}")

    df = pd.read_csv(filepath, index_col="parameter")
    calibration = {}
    for well in df.columns:
        calibration[well] = df[well].to_dict()
    return calibration


def parse_header_line(header_line):
    """
    Parse the header line (e.g., "Date [A Gr.1 Main] ...") and return a list of column names
    with meaningful keys (e.g., "C2_oxygen_raw", "A2_optical_temperature").
    """
    # Split by tab
    cols = header_line.strip().split('\t')

    # Define patterns to identify column types
    # We'll use regex to extract well names and channel types
    patterns = {
        'temperature': re.compile(r'$A Gr\.1 Main$'),  # Optical Temp
        'oxygen': re.compile(r'$A Gr\.2 Main$'),       # Oxygen (C2, E2, G2)
        'compT': re.compile(r'$A Gr\.2 CompT$'),       # Comp Temp
        'compP': re.compile(r'$A Gr\.2.%s CompP$'),    # Comp Pressure (dynamic)
    }

    # We'll build a list of (col_name, key) tuples
    parsed_cols = []
    well_mapping = {}  # To map raw well names to standardized ones

    for i, col in enumerate(cols):
        col = col.strip()

        # Skip empty
        if not col:
            continue

        # Extract well name from the column name (e.g., "C2", "E2", "G2")
        # Look for patterns like: [A Gr.2 Main] → C2, E2, G2
        # Or: [A Gr.2.CompT] → A2
        # Or: [A Gr.2.%s CompP] → C2, E2, G2

        # Try to extract well from the label
        well_match = re.search(r'(\w\d)', col)
        if not well_match:
            # Fallback: try to extract from the channel group
            if 'Main' in col and 'Gr.1' in col:
                well = 'A2'  # Default for temp
            elif 'Main' in col and 'Gr.2' in col:
                well = 'C2'  # Default for O2
            elif 'CompT' in col:
                well = 'A2'
            elif 'CompP' in col:
                well = 'C2'  # Placeholder
            else:
                well = 'unknown'
        else:
            well = well_match.group(1)

        # Determine channel type
        if patterns['temperature'].search(col):
            # Optical Temp: e.g., "Optical Temp. ( C) [A Gr.1.A2 Main]"
            key = f"{well}_optical_temperature"
        elif patterns['oxygen'].search(col):
            # Oxygen: e.g., "Oxygen ( mol/L) [A Gr.2.C2 Main]"
            key = f"{well}_oxygen_raw"
        elif patterns['compT'].search(col):
            # Comp Temp: e.g., "Optical Temp. ( C) [A Gr.2.A2 CompT]"
            key = f"{well}_comp_temperature"
        elif patterns['compP'].search(col):
            # Comp Pressure: e.g., "Pressure (mbar) [A Gr.2.C2 CompP]"
            key = f"{well}_comp_pressure"
        else:
            # Fallback: use raw column name
            key = col.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')

        # Store mapping
        parsed_cols.append((col, key))

    return parsed_cols


def process_oxygen_data(directory, metadata_dict, well_mapping_file="data/well_mapping.csv"):
    """
    Process FirePlate O2 data for one well.

    Parameters:
    -----------
    metadata_dict : dict
        - 'File name O2': name of the data file (e.g., "AE-772-1.txt")
        - 'calibration_file': path to calibration CSV file
        - 'output_folder': path to save results (optional, defaults to 'results')
        - 'Well': well name from overview.csv (e.g., "A1")

    well_mapping_file : str
        Path to the well mapping CSV file (relative to current directory)
    """
    # === 1. Extract metadata ===
    file_name = metadata_dict['File name O2']
    calibration_file = f"data/{metadata_dict['File name calibration']}"
    output_folder = metadata_dict.get('output_folder', 'results')
    well = metadata_dict['Well']  # ✅ Get well from metadata_dict

    # Build full path
    data_dir = Path("data")
    file_O2 = data_dir / file_name

    # Create output folder
    output_dir = Path(output_folder)
    output_dir.mkdir(exist_ok=True)

    # === 2. Load Well Mapping ===
    mapping_path = Path(well_mapping_file)
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

    mapping_df = pd.read_csv(mapping_path)
    mapping_dict = dict(zip(mapping_df['experiment_well'], mapping_df['fireplate_well']))

    if well not in mapping_dict:
        raise ValueError(f"Unknown well '{well}' in mapping file. Available: {list(mapping_dict.keys())}")

    fireplate_well = mapping_dict[well]
    print(f"Mapping: {well} → {fireplate_well}")

    # === 3. Load Calibration ===
    calibration = load_calibration_from_file(calibration_file)

    # === 4. Check Calibration ===
    if fireplate_well not in calibration.keys():
        raise ValueError(f"Calibration not found for well '{fireplate_well}'. Available: {list(calibration.keys())}")

    # === 5. Load Data ===
    with open(file_O2, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    # Find start of data
    data_start = None
    header_line = None
    for i, line in enumerate(lines):
        if line.startswith("Date [A Gr.1 Main]"):
            data_start = i + 1
            header_line = line.strip()
            break

    if data_start is None:
        raise RuntimeError("Could not find measurement data in file. Check the file path.")

    # Parse header to get dynamic column names
    parsed_columns = parse_header_line(header_line)

    # Build column mapping: raw name → meaningful key
    col_map = {raw_name: key for raw_name, key in parsed_columns}

    # Read data rows
    rows = []
    for line in lines[data_start:]:
        if not line.strip() or line.startswith("#"):
            continue
        row = pd.read_csv(StringIO(line), delimiter="\t", header=None).iloc[0].tolist()
        row += [""] * (len(parsed_columns) - len(row))
        rows.append(row[:len(parsed_columns)])

    # Build DataFrame with dynamic column names
    df = pd.DataFrame(rows, columns=[col_map[col] for col in header_line.strip().split('\t')])

    # Clean up: remove empty rows
    df = df[df["date_temp"].str.strip() != ""].reset_index(drop=True)

    # Set index: combine date and time
    df.index = pd.to_datetime(
        df["date_temp"] + " " + df["time_temp"],
        dayfirst=True,
        errors="coerce"
    )
    df.index.name = "date_time"

    # Convert numeric columns
    numeric_cols = [
        "dt_temp", "dt_o2", "dt_compT", "dt_compP",
        "A2_optical_temperature", "A2_comp_temperature", "pressure_mbar"
    ]

    # Add all dphi columns from calibration
    for well in calibration.keys():
        numeric_cols.append(f"{well}_dphi")

    # Convert only existing columns
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # === 6. Recalculate O2 (pO2 → µmol/L) ===
    temperature = df["A2_optical_temperature"]  # Use temp from A2
    salinity = 0.0

    # Use the target well's dphi column
    dphi_col = f"{fireplate_well}_dphi"
    if dphi_col not in df.columns:
        raise ValueError(f"Column '{dphi_col}' not found in data. Available: {list(df.columns)}")

    pO2 = calculate_pO2_from_calibration(
        dphi        = df[dphi_col],
        temperature = temperature,
        calibration = calibration[fireplate_well],
    )

    oxygen_uM = hPa_to_uM(
        data        = pO2,
        temperature = temperature,
        salinity    = salinity,
    )

    raw_data_dict = {
        fireplate_well: {
            'O2_time_s': df['dt_o2'].to_numpy(),
            'O2_data': oxygen_uM.to_numpy(),
            'O2_temperature': temperature.to_numpy()
        }
    }

    # === 7. Return only the essential data ===
    return raw_data_dict