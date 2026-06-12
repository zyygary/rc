# Radiative Cooling Reproducibility Package

This repository contains the source code, material database, spectral data, and FDTD assets used to reproduce the radiative-cooling simulations in this project. It is intended to be shared with reviewers as a fully open reproducibility package.

## Contents

- `main_app.py`: main PySide2 desktop entry point; loads the material/spectral managers, creates the five-tab main window, and supports runtime language switching
- `main_app_en.py`: thin English launcher that starts the same `MainWindow` with `LANGUAGE_EN`
- `main_app.spec`: PyInstaller spec file for packaging the desktop application
- `vision.py`: standalone material-preview script that interpolates every material file and saves `n/k` comparison plots to `_material_previews/`
- `test_efield.py`: standalone PySide2 + pyqtgraph tool for visualizing the 2D internal electric-field intensity map of a multilayer stack while sweeping the MgF2 thickness
- `test_integration_limits.py`: diagnostic script for overriding solar/thermal integration limits and checking how `P_sum`, `P_atm`, and equilibrium temperature change
- `core/constants.py`: shared physical constants, wavelength grid definition, and canonical `data/` and `materials/` paths
- `core/material_manager.py`: loads optical-constant text files, validates/parses them, supports adding new material files, and interpolates complex refractive indices onto the simulation grid
- `core/spectral_manager.py`: loads the solar spectrum and atmospheric transmittance data, interpolates them onto the common wavelength grid, builds blackbody spectra, and prepares the default solar/thermal integration windows
- `core/tmm_core.py`: vectorized transfer-matrix implementation for spectral scans and angle scans, returning `R_s` and `R_p`
- `core/cooling_calculator.py`: radiative-cooling post-processing routines for `P_sum`, `P_rad`, `P_atm`, non-radiative loss, temperature sweeps, and equilibrium-temperature solving
- `core/utils.py`: helper functions for parsing compact layer-stack strings and computing weighted emissivity/reflectance averages
- `core/__init__.py`: package marker for the numerical core
- `ui/material_viewer_widget.py`: materials tab for browsing loaded materials, plotting `n/k`, and importing additional `.txt` optical-constant files
- `ui/tmm_simulator_widget.py`: main TMM workflow tab for defining multilayer stacks, running spectral calculations, and displaying reflectance/emissivity results
- `ui/tmm_simulator_layout.py`: layout builder used by the TMM simulator tab
- `ui/layer_widget.py`: reusable single-layer row widget with material selection, thickness entry, and add/remove controls
- `ui/sweep_widget.py`: parameter-sweep tab for single-layer thickness scans, 2D heatmaps, and slider-driven exploration of stack response
- `ui/angle_scan_widget.py`: angle-scan tab that reuses the structure from the TMM tab and evaluates angular optical response for different polarizations
- `ui/cooling_widget.py`: radiative-cooling tab for loading a structure, computing `P_atm`/`P_sum`, sweeping `T_sample`, and reporting equilibrium temperature
- `ui/i18n.py`: minimal language-switch helper with `zh/en` normalization and text selection
- `ui/reviewer_english.py`: helper that forces a window into English review mode
- `ui/styles.py`: application-wide Qt stylesheet and pyqtgraph theme setup
- `ui/__init__.py`: package marker for the UI module
- `materials/*.txt`: plain-text optical constants for the materials used by the simulator, typically stored as wavelength with `n` and optional `k`
- `data/solar_spectrum.txt`: solar irradiance input used for the solar-band weighting and `P_sum` calculation
- `data/atm_transmittance.txt`: atmospheric transmittance input used for the atmospheric-window weighting and `P_atm` calculation
- `FDTD/ALL.fsp`: FDTD project file for the complementary full-wave simulation case

## Environment

Recommended Python version:

- Python 3.9 to 3.12

Main Python dependencies:

- `numpy`
- `scipy`
- `PySide2`
- `pyqtgraph`
- `matplotlib` for auxiliary plotting scripts

Example installation:

```bash
pip install numpy scipy PySide2 pyqtgraph matplotlib
```

## Running the GUI

Chinese/default interface:

```bash
python main_app.py
```

English interface:

```bash
python main_app_en.py
```

The application supports runtime language switching from the `Language` menu.

## Reproducing TMM Results

1. Open `main_app.py` or `main_app_en.py`.
2. In the TMM tab, define the multilayer stack and click the calculation button.
3. Use the Sweep tab for thickness sweeps and 2D heatmaps.
4. Use the Angle tab for angle-dependent weighted optical response.
5. Use the Cooling tab to load the TMM spectrum and compute `P_cool` and `T_eq`.

Default example stack currently preloaded in the GUI:

- `PMMA (1068 nm)`
- `SiO2 (6749 nm)`
- `TiO2 (4675 nm)`
- `Ag (200 nm)`
- `Si substrate`

## Reproducing FDTD Results

The `FDTD/ALL.fsp` file is included as the corresponding FDTD project for full-wave reproduction. Open it with your FDTD software environment and run it using the solver settings stored in the project file.

Because the FDTD project is large, this repository stores it with Git LFS.

## Notes for Reviewers

- Material files are plain text and can be inspected directly.
- Solar and atmospheric input spectra are included locally in `data/`.
- The English GUI now covers both static labels and dynamic runtime text.
- No external web service is required to run the numerical core.

## Repository Scope

This repository is intended to be made public for peer-review reproducibility. Local IDE files, caches, and generated preview artifacts are intentionally excluded.
