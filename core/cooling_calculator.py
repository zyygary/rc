import numpy as np
from scipy.interpolate import interp1d
from scipy.integrate import quad
from scipy.optimize import brentq
from core.spectral_manager import SpectralDataManager
from typing import List, Tuple

C1_PLANCK_UM = 1.1926e8
C2_PLANCK_UM = 14388


def calculate_Ibb_um_scalar(T: float, lambda_um_scalar: float) -> float:
    if T < 1e-6 or lambda_um_scalar < 1e-3: return 0.0
    exponent = C2_PLANCK_UM / (lambda_um_scalar * T)
    if exponent > 700: exponent = 700
    denominator = (lambda_um_scalar ** 5) * (np.exp(exponent) - 1)
    if denominator < 1e-100: return 0.0
    return C1_PLANCK_UM / denominator


def calculate_P_sum(absorptance: np.ndarray, spec: SpectralDataManager) -> float:
    interp_absorptance_m = interp1d(spec.lambda_m.flatten(), absorptance, kind='linear', bounds_error=False,
                                    fill_value=0.0)
    absorptance_on_um_grid = interp_absorptance_m(spec.lambda_um * 1e-6)
    integrand = spec.IAM1_5[spec.idx_solar] * absorptance_on_um_grid[spec.idx_solar]
    P_sum = np.trapz(
        integrand,
        spec.lambda_um[spec.idx_solar]
    )
    return P_sum


def calculate_P_rad(T_sample: float, absorptance: np.ndarray, spec: SpectralDataManager) -> float:
    interp_absorptance_m = interp1d(spec.lambda_m.flatten(), absorptance, kind='linear', bounds_error=False,
                                    fill_value=0.0)
    absorptance_on_um_grid = interp_absorptance_m(spec.lambda_um * 1e-6)
    Ibb_um_on_grid = np.array([calculate_Ibb_um_scalar(T_sample, lam) for lam in spec.lambda_um])
    idx_thermal = spec.idx_thermal
    integrand_1D = Ibb_um_on_grid[idx_thermal] * absorptance_on_um_grid[idx_thermal]
    integral = np.trapz(
        integrand_1D,
        spec.lambda_um[idx_thermal]
    )
    return np.pi * integral


class _HemisphericalAtmIntegrator:
    """
    此类预先计算 F(tau) = integral( (1 - tau^(1/c(t))) * s(t)c(t) dt )
    的查找表 (LUT), 并提供一个快速的插值函数。
    它只在第一次调用 calculate_P_atm 时计算一次。
    """
    _instance = None

    def __init__(self):
        print("--- [REFACTOR V5] 正在构建 F(tau) 角度积分查找表... ---")
        self.tau_lut_x = np.linspace(0.0, 1.0, 100)
        self.F_lut_y = np.zeros_like(self.tau_lut_x)

        for i, tau_val in enumerate(self.tau_lut_x):
            if tau_val < 1e-9:
                self.F_lut_y[i] = 0.5
            elif tau_val > 0.999999:
                self.F_lut_y[i] = 0.0
            else:
                try:
                    val, _ = quad(
                        self._theta_integrand,
                        0, np.pi / 2,
                        args=(tau_val,),
                        epsrel=1e-3
                    )
                    self.F_lut_y[i] = val
                except Exception as e:
                    print(f"*** 警告: F(tau) LUT build failed at tau={tau_val}: {e} ***")
                    self.F_lut_y[i] = 0.0

        self.interp_F_of_tau = interp1d(self.tau_lut_x, self.F_lut_y, kind='linear')
        print("--- [REFACTOR V5] F(tau) 查找表构建完毕。 ---")

    @staticmethod
    def _theta_integrand(theta: float, tau: float) -> float:
        """
        被积函数: (1 - tau^(1/cos(theta))) * sin(theta) * cos(theta)
        """
        cos_theta = np.cos(theta)
        if cos_theta < 1e-9:
            return 0.0

        power_term = 1.0 / cos_theta
        if power_term > 700 and tau < 1.0:
            return np.sin(theta) * cos_theta

        tau_powered = np.power(tau, power_term)
        return (1.0 - tau_powered) * np.sin(theta) * cos_theta

    def get_F_values(self, tau_array: np.ndarray) -> np.ndarray:
        """
        在 F(tau) 查找表上插值一个 (10w+) 点的数组。
        """
        tau_array_clipped = np.clip(tau_array, 0.0, 1.0)
        return self.interp_F_of_tau(tau_array_clipped)

    @classmethod
    def get_instance(cls):
        """
        使用单例模式, 确保 F(tau) LUT 只构建一次。
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def calculate_P_atm(T_amb: float, absorptance: np.ndarray, spec: SpectralDataManager) -> float:
    """
    [REFACTOR V5] 计算 P_atm (大气吸收)

    使用解耦的 1D 积分 (np.trapz) 在高精度网格 (10w+ 点) 上运行,
    以完美捕捉尖峰。

    P_atm = 2*pi * integral( Ibb(L) * alpha(L) * F(tau(L)) dL )
    """

    print("--- [REFACTOR V5] 正在执行高精度 1D P_atm 计算... ---")

    F_tau_integrator = _HemisphericalAtmIntegrator.get_instance()

    if not hasattr(spec, 'atm_lambda_um_raw'):
        raise AttributeError("SpectralDataManager 缺少 'atm_lambda_um_raw'。请检查 spectral_manager.py。")

    lambda_high_res = spec.atm_lambda_um_raw
    tau_high_res = spec.atm_tau_raw

    interp_absorptance_m = interp1d(
        spec.lambda_m.flatten(),
        absorptance,
        kind='linear',
        bounds_error=False,
        fill_value=0.0
    )

    def interp_alpha_um(lambda_um_array: np.ndarray) -> np.ndarray:
        return interp_absorptance_m(lambda_um_array * 1e-6)

    def interp_Ibb_um(lambda_um_array: np.ndarray) -> np.ndarray:
        return np.array([calculate_Ibb_um_scalar(T_amb, lam) for lam in lambda_um_array])

    idx_high_res_slice = np.where(
        (lambda_high_res >= 8.0) & (lambda_high_res <= 13.0)
    )[0]

    if idx_high_res_slice.size < 2:
        print("*** 警告: 高精度大气数据在 8-13um 范围内没有足够的点。P_atm 将为 0。")
        return 0.0

    lambda_slice = lambda_high_res[idx_high_res_slice]
    tau_slice = tau_high_res[idx_high_res_slice]

    alpha_slice = interp_alpha_um(lambda_slice)
    Ibb_slice = interp_Ibb_um(lambda_slice)

    F_slice = F_tau_integrator.get_F_values(tau_slice)

    integrand_1D = Ibb_slice * alpha_slice * F_slice

    integral = np.trapz(integrand_1D, lambda_slice)

    Patm = 2 * np.pi * integral

    print(f"--- [REFACTOR V5] 高精度 P_atm 计算完毕: {Patm:.4f} W/m^2 ---")

    return Patm


def calculate_P_non(T_sample: float, T_amb: float, hc: float) -> float:
    return hc * (T_amb - T_sample)


def run_cooling_sweep(
        absorptance_spectrum: np.ndarray,
        spectral_manager: SpectralDataManager,
        T_amb: float,
        hc_values: List[float],
        T_sample_range: np.ndarray,
        P_atm: float,
        P_sum: float
) -> Tuple[np.ndarray, np.ndarray]:
    N_T = len(T_sample_range)
    N_hc = len(hc_values)
    Pcool_matrix = np.zeros((N_T, N_hc))

    print("... 正在扫描 T_sample (使用快速 Prad)...")

    for hc_idx, hc in enumerate(hc_values):
        for T_idx, T_sample in enumerate(T_sample_range):
            P_rad = calculate_P_rad(T_sample, absorptance_spectrum, spectral_manager)
            P_non = calculate_P_non(T_sample, T_amb, hc)
            Pcool = P_rad - P_atm - P_sum - P_non
            Pcool_matrix[T_idx, hc_idx] = Pcool

    print("... 扫描完成 ...")
    return T_sample_range, Pcool_matrix


def calculate_Pcool_for_T(
        T_sample: float,
        T_amb: float,
        hc: float,
        P_atm: float,
        P_sum: float,
        absorptance: np.ndarray,
        spec: SpectralDataManager
) -> float:
    P_rad = calculate_P_rad(T_sample, absorptance, spec)
    P_non = calculate_P_non(T_sample, T_amb, hc)
    return P_rad - P_atm - P_sum - P_non


def find_equilibrium_temp(
        hc_value: float,
        T_amb: float,
        P_atm: float,
        P_sum: float,
        absorptance: np.ndarray,
        spec: SpectralDataManager
) -> Tuple[float, float]:
    def objective_func(T_sample: float) -> float:
        return calculate_Pcool_for_T(
            T_sample, T_amb, hc_value, P_atm, P_sum, absorptance, spec
        )

    try:
        T_eq = brentq(objective_func, 200.0, T_amb + 50.0)
        T_drop = T_amb - T_eq
        return T_eq, T_drop
    except ValueError as e:
        print(f"*** 寻根失败: {e}. 可能在该范围内没有平衡点。 ***")
        return np.nan, np.nan