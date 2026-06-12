import os
import numpy as np

C_LIGHT = 299792458.0
H_PLANCK = 6.62607015e-34
K_BOLTZMANN = 1.380649e-23

C1_PLANCK_SI = 2 * H_PLANCK * (C_LIGHT ** 2)
C2_PLANCK_SI = (H_PLANCK * C_LIGHT) / K_BOLTZMANN

N_POINTS = 1000
LAMBDA_MIN_UM = 0.3
LAMBDA_MAX_UM = 14.0

LAMBDA_GRID_UM = np.linspace(LAMBDA_MIN_UM, LAMBDA_MAX_UM, N_POINTS)
LAMBDA_GRID_M = (LAMBDA_GRID_UM * 1e-6).reshape(-1, 1)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MATERIALS_DIR = os.path.join(BASE_DIR, 'materials')