import numpy as np
from typing import List, Dict, Any, Tuple


def calculate_TMM_core(layer_stack: List[Dict[str, Any]],
                       lambda_m: np.ndarray,
                       theta0_deg: float
                       ) -> Tuple[np.ndarray, np.ndarray]:
    """
    [V47] 核心 TMM 计算, 向量化 *波长* (lambda_m)。

    返回: (R_s, R_p)
    """

    theta0_rad = np.deg2rad(theta0_deg)
    N = len(lambda_m)

    M_total_s = np.zeros((N, 2, 2), dtype=complex)
    M_total_p = np.zeros((N, 2, 2), dtype=complex)
    M_total_s[:, 0, 0] = 1.0
    M_total_s[:, 1, 1] = 1.0
    M_total_p[:, 0, 0] = 1.0
    M_total_p[:, 1, 1] = 1.0

    n_air = np.ones((N, 1), dtype=complex)
    cos_theta_air = np.cos(theta0_rad)
    sin_theta_air = np.sin(theta0_rad)

    eta_air_s = cos_theta_air * n_air
    eta_air_p = n_air / cos_theta_air

    n_sub = layer_stack[-1]['n']
    sin_theta_sub = n_air * sin_theta_air / n_sub
    cos_theta_sub = np.lib.scimath.sqrt(1.0 - sin_theta_sub ** 2)
    eta_sub_s = n_sub * cos_theta_sub
    eta_sub_p = n_sub / cos_theta_sub

    for layer in layer_stack[:-1]:
        n_layer = layer['n']
        d_layer = layer['d']

        sin_theta_layer = n_air * sin_theta_air / n_layer
        cos_theta_layer = np.lib.scimath.sqrt(1.0 - sin_theta_layer ** 2)

        eta_s = n_layer * cos_theta_layer
        eta_p = n_layer / cos_theta_layer
        delta = (2 * np.pi * d_layer / lambda_m) * n_layer * cos_theta_layer

        cos_delta = np.cos(delta)
        sin_delta = np.sin(delta)

        M_s = np.zeros((N, 2, 2), dtype=complex)
        M_s[:, 0, 0] = cos_delta.flatten()
        M_s[:, 0, 1] = (-1j * sin_delta / eta_s).flatten()
        M_s[:, 1, 0] = (-1j * sin_delta * eta_s).flatten()
        M_s[:, 1, 1] = cos_delta.flatten()

        M_p = np.zeros((N, 2, 2), dtype=complex)
        M_p[:, 0, 0] = cos_delta.flatten()
        M_p[:, 0, 1] = (-1j * sin_delta / eta_p).flatten()
        M_p[:, 1, 0] = (-1j * sin_delta * eta_p).flatten()
        M_p[:, 1, 1] = cos_delta.flatten()

        M_total_s = np.einsum('nij,njk->nik', M_total_s, M_s)
        M_total_p = np.einsum('nij,njk->nik', M_total_p, M_p)

    M11_s = M_total_s[:, 0, 0].reshape(-1, 1)
    M12_s = M_total_s[:, 0, 1].reshape(-1, 1)
    M21_s = M_total_s[:, 1, 0].reshape(-1, 1)
    M22_s = M_total_s[:, 1, 1].reshape(-1, 1)
    num_s = (eta_air_s * M11_s + eta_air_s * eta_sub_s * M12_s) - (M21_s + eta_sub_s * M22_s)
    den_s = (eta_air_s * M11_s + eta_air_s * eta_sub_s * M12_s) + (M21_s + eta_sub_s * M22_s)
    r_s = num_s / den_s

    M11_p = M_total_p[:, 0, 0].reshape(-1, 1)
    M12_p = M_total_p[:, 0, 1].reshape(-1, 1)
    M21_p = M_total_p[:, 1, 0].reshape(-1, 1)
    M22_p = M_total_p[:, 1, 1].reshape(-1, 1)
    num_p = (eta_air_p * M11_p + eta_air_p * eta_sub_p * M12_p) - (M21_p + eta_sub_p * M22_p)
    den_p = (eta_air_p * M11_p + eta_air_p * eta_sub_p * M12_p) + (M21_p + eta_sub_p * M22_p)
    r_p = num_p / den_p

    R_s = (np.abs(r_s) ** 2).flatten()
    R_p = (np.abs(r_p) ** 2).flatten()

    return R_s, R_p


def calculate_TMM_angle_scan(layer_stack: List[Dict[str, Any]],
                             lambda_m: float,
                             angles_deg: np.ndarray
                             ) -> Tuple[np.ndarray, np.ndarray]:
    """
    [V47] TMM 计算, 向量化 *角度* (angles_deg)。

    注意:
    - 'layer_stack' 必须包含 *标量* 复折射率
    - 'lambda_m' 必须是 *标量* 浮点数

    返回: (R_s, R_p)
    """

    N = len(angles_deg)
    theta0_rad = np.deg2rad(angles_deg).reshape(1, N)

    M_total_s = np.zeros((N, 2, 2), dtype=complex)
    M_total_p = np.zeros((N, 2, 2), dtype=complex)
    M_total_s[:, 0, 0] = 1.0
    M_total_s[:, 1, 1] = 1.0
    M_total_p[:, 0, 0] = 1.0
    M_total_p[:, 1, 1] = 1.0

    n_air = 1.0 + 0j
    cos_theta_air = np.cos(theta0_rad)
    sin_theta_air = np.sin(theta0_rad)

    eta_air_s = cos_theta_air * n_air
    eta_air_p = n_air / cos_theta_air

    n_sub = layer_stack[-1]['n']
    sin_theta_sub = n_air * sin_theta_air / n_sub
    cos_theta_sub = np.lib.scimath.sqrt(1.0 - sin_theta_sub ** 2)
    eta_sub_s = n_sub * cos_theta_sub
    eta_sub_p = n_sub / cos_theta_sub

    for layer in layer_stack[:-1]:
        n_layer = layer['n']
        d_layer = layer['d']

        sin_theta_layer = n_air * sin_theta_air / n_layer
        cos_theta_layer = np.lib.scimath.sqrt(1.0 - sin_theta_layer ** 2)

        eta_s = n_layer * cos_theta_layer
        eta_p = n_layer / cos_theta_layer
        delta = (2 * np.pi * d_layer / lambda_m) * n_layer * cos_theta_layer

        cos_delta = np.cos(delta)
        sin_delta = np.sin(delta)

        M_s = np.zeros((N, 2, 2), dtype=complex)
        M_s[:, 0, 0] = cos_delta.flatten()
        M_s[:, 0, 1] = (-1j * sin_delta / eta_s).flatten()
        M_s[:, 1, 0] = (-1j * sin_delta * eta_s).flatten()
        M_s[:, 1, 1] = cos_delta.flatten()

        M_p = np.zeros((N, 2, 2), dtype=complex)
        M_p[:, 0, 0] = cos_delta.flatten()
        M_p[:, 0, 1] = (-1j * sin_delta / eta_p).flatten()
        M_p[:, 1, 0] = (-1j * sin_delta * eta_p).flatten()
        M_p[:, 1, 1] = cos_delta.flatten()

        M_total_s = np.einsum('nij,njk->nik', M_total_s, M_s)
        M_total_p = np.einsum('nij,njk->nik', M_total_p, M_p)

    M11_s = M_total_s[:, 0, 0].reshape(1, N)
    M12_s = M_total_s[:, 0, 1].reshape(1, N)
    M21_s = M_total_s[:, 1, 0].reshape(1, N)
    M22_s = M_total_s[:, 1, 1].reshape(1, N)
    num_s = (eta_air_s * M11_s + eta_air_s * eta_sub_s * M12_s) - (M21_s + eta_sub_s * M22_s)
    den_s = (eta_air_s * M11_s + eta_air_s * eta_sub_s * M12_s) + (M21_s + eta_sub_s * M22_s)
    r_s = num_s / den_s

    M11_p = M_total_p[:, 0, 0].reshape(1, N)
    M12_p = M_total_p[:, 0, 1].reshape(1, N)
    M21_p = M_total_p[:, 1, 0].reshape(1, N)
    M22_p = M_total_p[:, 1, 1].reshape(1, N)
    num_p = (eta_air_p * M11_p + eta_air_p * eta_sub_p * M12_p) - (M21_p + eta_sub_p * M22_p)
    den_p = (eta_air_p * M11_p + eta_air_p * eta_sub_p * M12_p) + (M21_p + eta_sub_p * M22_p)
    r_p = num_p / den_p

    R_s = (np.abs(r_s) ** 2).flatten()
    R_p = (np.abs(r_p) ** 2).flatten()

    return R_s, R_p