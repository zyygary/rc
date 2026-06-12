# Radiative Cooling Reproducibility Package

This repository contains the source code, material database, spectral data, and FDTD assets used to reproduce the radiative-cooling simulations in this project. It is intended to be shared with reviewers as a fully open reproducibility package.

## Contents

- `main_app.py`: main desktop application entry point
- `main_app_en.py`: English entry point
- `core/`: numerical core for TMM, spectra loading, and cooling-power calculations
- `ui/`: PySide2 user interface for materials, TMM simulation, sweep, angle scan, and cooling analysis
- `materials/`: optical-constant text files used by the simulator
- `data/`: solar spectrum and atmospheric transmittance input data
- `FDTD/`: FDTD project files used for complementary full-wave simulations
- `test_efield.py`: electric-field visualization helper
- `test_integration_limits.py`: cooling/integration sensitivity script
- `vision.py`: material interpolation preview utility

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
