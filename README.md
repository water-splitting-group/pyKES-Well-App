# pyKES Well App

This repository packages a Streamlit workflow built on top of `pyKES` for well-based experiment analysis. It provides scaffolding for ingesting experiment metadata plus raw sensor files, processing the time series, and visualizing the resulting dataset.
 
## What It Does

The app provides three main steps:

1. Upload experiment metadata and raw measurement files.
2. Inspect time-series plots for raw, smoothed, and rate-derived signals.
3. Review analysis results such as extracted maximum rates.

## Requirements

- Python 3.9 or newer
- `pyKES>=0.2.0`
- `numpy>=1.24.4`
- `pandas>=2.0.3`
- `scipy>=1.10.1`

## Install

From the repository root:

```bash
pip install -e .
```

If you are using an existing environment that already contains the dependencies, make sure `pyKES` is available before launching the app.

## Run Locally

The Streamlit entrypoint is [`src/pykes_well_app/streamlit_app/Home.py`](src/pykes_well_app/streamlit_app/Home.py).

```bash
streamlit run src/pykes_well_app/streamlit_app/Home.py
```

The app configuration lives in [`src/pykes_well_app/config.py`](src/pykes_well_app/config.py). It wires together the metadata lookup, raw file readers, and processing functions used by the upload page.

## Static Deploy

The repository also includes a static deploy setup in [`deploy/`](deploy/). To rebuild the browser bundle and serve it locally:

```bash
python deploy/build.py
cd deploy
python -m http.server 8000
```

Then open `http://localhost:8000` in a browser.

`build.py` writes both the app sources and the requirement list that stlite installs in
the browser into `deploy/files.js`, so [`deploy/index.html`](deploy/index.html) holds no
version numbers. The `pyKES` requirement is pinned to the version resolved in `uv.lock`;
bumping it is therefore

```bash
uv lock --upgrade-package pykes
```

(raising the floor in [`pyproject.toml`](pyproject.toml) first if a newer release is
needed). A pin left behind by hand used to make the deployed app fail on import of
modules added in the meantime.

* Raising floor in [`pyproject.toml`](pyproject.toml), then
```bash
uv lock --refresh
uv sync
```

## Versioning

* Updating version in [`pyproject.toml`](pyproject.toml)
```bash
git tag v0.1.1
git push origin v0.1.1
```
* Creating release from tag in GitHub


## Repository Layout

- [`src/pykes_well_app/data_parsing/`](src/pykes_well_app/data_parsing/) contains the raw readers and signal-processing helpers.
- [`src/pykes_well_app/streamlit_app/`](src/pykes_well_app/streamlit_app/) contains the Streamlit entrypoint and pages.
- [`data/`](data/) stores example measurement files used for local development and testing.
- [`deploy/`](deploy/) contains the static browser bundle entrypoint and build script.

## Contributing

Contributions are welcome. Please open a pull request if you want to propose a change.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
