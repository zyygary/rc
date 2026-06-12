import numpy as np
from typing import List, Tuple
from core.spectral_manager import SpectralDataManager


def parse_input_string(input_str: str) -> Tuple[List[str], List[int]]:
    print(f"[Parser V49] 正在解析: {input_str}")
    parts = input_str.strip().split()
    if not parts:
        raise ValueError("输入为空。")
    mats = []
    nums = []
    for part in parts:
        try:
            val = float(part)
            nums.append(val)
        except ValueError:
            mats.append(part)
    print(f"[Parser V49] 分离后: Mats={mats}, Nums={nums}")
    n_layers = len(mats)
    if n_layers == 0:
        raise ValueError("未找到材料名称。")
    if len(nums) != n_layers:
        raise ValueError(f"材料数量 ({n_layers}) 与厚度/数字数量 ({len(nums)}) 必须完全一致。")
    thicknesses_nm = [int(round(n)) for n in nums]
    print(f"[Parser V49] 成功: Mats={mats}, Thicks (Rounded)={thicknesses_nm}")
    return mats, thicknesses_nm


def calculate_weighted_averages(
        epsilon_spectrum: np.ndarray,
        rho_spectrum: np.ndarray,
        spectral_manager: SpectralDataManager
) -> Tuple[float, float]:
    """
    [V47 修正]
    计算 *任何给定光谱* 的加权平均发射率 (epsilon_bar) 和反射率 (rho_bar)
    """
    spec = spectral_manager

    numerator_epsilon = np.trapz(
        spec.I_bb[spec.idx_thermal].flatten() * epsilon_spectrum[spec.idx_thermal],
        spec.lambda_m[spec.idx_thermal].flatten()
    )
    epsilon_bar = numerator_epsilon / spec.denominator_epsilon

    numerator_rho = np.trapz(
        spec.IAM1_5[spec.idx_solar] * rho_spectrum[spec.idx_solar],
        spec.lambda_um[spec.idx_solar]
    )
    rho_bar = numerator_rho / spec.denominator_rho
    return epsilon_bar, rho_bar