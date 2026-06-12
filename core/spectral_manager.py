import os
import numpy as np
from scipy.interpolate import interp1d

from core.constants import (
    DATA_DIR, H_PLANCK, C_LIGHT, K_BOLTZMANN,
    LAMBDA_GRID_UM, LAMBDA_GRID_M
)


class SpectralDataManager:
    """
    (在 App 启动时运行一次)
    加载光谱数据和计算黑体辐射。
    """

    atm_lambda_um_raw: np.ndarray
    atm_tau_raw: np.ndarray

    def __init__(self, data_dir=DATA_DIR):
        self.lambda_um = LAMBDA_GRID_UM
        self.lambda_m = LAMBDA_GRID_M

        try:
            solar_path = os.path.join(data_dir, 'solar_spectrum.txt')
            print(f"  > 正在加载: {solar_path}")

            solar_data_raw = np.genfromtxt(solar_path, comments='#')

            if solar_data_raw.size == 0:
                raise ValueError(f"从 {solar_path} 加载的数据为空。")
            if solar_data_raw.ndim == 1:
                solar_data_raw = solar_data_raw.reshape(1, -1)
            if solar_data_raw.shape[1] < 2:
                raise ValueError(f"文件 {solar_path} 的列数 < 2。")

            w_raw_nm = solar_data_raw[:, 0]
            i_raw_nm = solar_data_raw[:, 1]

            w_raw_um_solar = w_raw_nm / 1000.0

            i_raw_um = i_raw_nm * 1000.0

            w_unique_um, idx_unique_um = np.unique(w_raw_um_solar, return_index=True)
            i_unique_um = i_raw_um[idx_unique_um]

            if len(w_unique_um) < 2:
                raise ValueError(f"在 {solar_path} 中找到的有效唯一数据点 < 2。")

            interp_func = interp1d(w_unique_um, i_unique_um, kind='linear', bounds_error=False, fill_value=0)
            self.IAM1_5 = interp_func(self.lambda_um)

        except Exception as e:
            print(f"*** 严重错误: 无法加载 'solar_spectrum.txt': {e} ***")
            raise e

        try:
            atm_path = os.path.join(data_dir, 'atm_transmittance.txt')
            print(f"  > 正在加载: {atm_path}")

            atm_data_raw = np.genfromtxt(atm_path, comments='#')

            if atm_data_raw.size == 0:
                raise ValueError(f"从 {atm_path} 加载的数据为空。")
            if atm_data_raw.ndim == 1:
                atm_data_raw = atm_data_raw.reshape(1, -1)
            if atm_data_raw.shape[1] < 2:
                raise ValueError(f"文件 {atm_path} 的列数 < 2。")

            w_raw_m = atm_data_raw[:, 0]
            w_raw_um_atm = w_raw_m
            t_raw_atm = atm_data_raw[:, 1]

            w_unique_atm, idx_unique_atm = np.unique(w_raw_um_atm, return_index=True)
            t_unique_atm = t_raw_atm[idx_unique_atm]

            if len(w_unique_atm) < 2:
                raise ValueError(f"在 {atm_path} 中找到的有效唯一数据点 < 2。 (文件格式是否正确？)")

            self.atm_lambda_um_raw = w_unique_atm
            self.atm_tau_raw = t_unique_atm
            print(f"  > [REFACTOR] 已加载 {len(self.atm_lambda_um_raw)} 个高分辨率大气数据点。")

            interp_func_atm = interp1d(w_unique_atm, t_unique_atm, kind='linear', bounds_error=False, fill_value=0)
            self.atm_transmittance = interp_func_atm(self.lambda_um)

        except Exception as e:
            print(f"*** 严重错误: 无法加载 'atm_transmittance.txt': {e} ***")
            raise e

        T = 300
        numerator = 2 * H_PLANCK * C_LIGHT ** 2
        exponent = (H_PLANCK * C_LIGHT) / (self.lambda_m * K_BOLTZMANN * T)
        denominator = (self.lambda_m ** 5) * (np.exp(exponent) - 1)
        self.I_bb = numerator / denominator

        self.idx_thermal = np.where((self.lambda_um >= 8) & (self.lambda_um <= 13))[0]
        self.idx_solar = np.where((self.lambda_um >= 0.3) & (self.lambda_um <= 2.5))[0]

        self.denominator_epsilon = np.trapz(
            self.I_bb[self.idx_thermal].flatten(),
            self.lambda_m[self.idx_thermal].flatten()
        )

        self.denominator_rho = np.trapz(
            self.IAM1_5[self.idx_solar],
            self.lambda_um[self.idx_solar]
        )
        if self.denominator_epsilon == 0 or self.denominator_rho == 0:
            if self.denominator_rho == 0:
                raise ValueError("太阳光谱积分(denominator_rho)为零。Psum Bug 仍然存在。")
            if self.denominator_epsilon == 0:
                raise ValueError(
                    "黑体辐射积分(denominator_epsilon)为零。请检查 core/constants.py 中的 LAMBDA_MAX_UM 是否大于 13。")
            raise ValueError("积分分母为零。")

        if np.any(self.IAM1_5):
            IAM1_5_norm_full = self.IAM1_5 / np.max(self.IAM1_5)
        else:
            print("*** 警告: 太阳光谱数据为空或全零, 无法归一化。 ***")
            IAM1_5_norm_full = np.zeros_like(self.IAM1_5)

        if np.any(self.I_bb):
            I_bb_norm_full = self.I_bb.flatten() / np.max(self.I_bb)
        else:
            print("*** 警告: 黑体辐射数据为空或全零, 无法归一化。 ***")
            I_bb_norm_full = np.zeros_like(self.I_bb.flatten())

        self.IAM1_5_norm_masked = np.zeros_like(IAM1_5_norm_full)
        self.I_bb_norm_masked = np.zeros_like(I_bb_norm_full)

        self.IAM1_5_norm_masked[self.idx_solar] = IAM1_5_norm_full[self.idx_solar]
        self.I_bb_norm_masked[self.idx_thermal] = I_bb_norm_full[self.idx_thermal]

        print("光谱管理器已初始化。")