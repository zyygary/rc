import numpy as np
import os
import sys
from typing import Tuple

# --- 1. 导入核心模块 (假定此脚本在项目根目录, 与 main_app.py 同级) ---
try:
    from core.material_manager import MaterialManager
    from core.spectral_manager import SpectralDataManager
    from core.constants import LAMBDA_GRID_UM
    from core.tmm_core import calculate_TMM_core
    # 导入整个冷却计算器模块, 以便我们可以调用它的所有函数
    import core.cooling_calculator as cooling_calc
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保此脚本与 'main_app.py' 放在同一项目根目录中,")
    print("并且 'core' 和 'ui' 目录是该根目录的子目录。")
    sys.exit(1)


# -----------------------------------------------------------------
# 2. [核心] "热补丁" 函数
# -----------------------------------------------------------------
def set_custom_integration_limits(
        spec: SpectralDataManager,
        solar_min: float, solar_max: float,
        thermal_min: float, thermal_max: float
) -> None:
    """
    在 SpectralDataManager 加载后, 强制覆盖其积分范围和依赖项。
    """
    print("--- [测试] 正在应用自定义积分范围... ---")
    print(f"  > 太阳波段: {solar_min} μm - {solar_max} μm")
    print(f"  > 热力波段: {thermal_min} μm - {thermal_max} μm")

    # A. 覆盖索引
    spec.idx_solar = np.where(
        (spec.lambda_um >= solar_min) & (spec.lambda_um <= solar_max)
    )[0]
    spec.idx_thermal = np.where(
        (spec.lambda_um >= thermal_min) & (spec.lambda_um <= thermal_max)
    )[0]

    # B. [关键] 重新计算依赖于索引的积分分母
    # (这部分逻辑复制自 spectral_manager.py)
    if spec.idx_thermal.size == 0:
        print("*** 警告: 自定义的热力波段为空 (没有数据点), denominator_epsilon 将为 0。 ***")
        spec.denominator_epsilon = 0.0
    else:
        spec.denominator_epsilon = np.trapz(
            spec.I_bb[spec.idx_thermal].flatten(),
            spec.lambda_m[spec.idx_thermal].flatten()
        )

    if spec.idx_solar.size == 0:
        print("*** 警告: 自定义的太阳波段为空 (没有数据点), denominator_rho 将为 0。 ***")
        spec.denominator_rho = 0.0
    else:
        spec.denominator_rho = np.trapz(
            spec.IAM1_5[spec.idx_solar],
            spec.lambda_um[spec.idx_solar]  # 使用 lambda_um (um)
        )

    # C. 重新计算用于绘图的遮罩 (可选, 但保持一致性)
    if np.any(spec.IAM1_5):
        IAM1_5_norm_full = spec.IAM1_5 / np.max(spec.IAM1_5)
    else:
        IAM1_5_norm_full = np.zeros_like(spec.IAM1_5)

    if np.any(spec.I_bb):
        I_bb_norm_full = spec.I_bb.flatten() / np.max(spec.I_bb)
    else:
        I_bb_norm_full = np.zeros_like(spec.I_bb.flatten())

    spec.IAM1_5_norm_masked = np.zeros_like(IAM1_5_norm_full)
    spec.I_bb_norm_masked = np.zeros_like(I_bb_norm_full)

    if spec.idx_solar.size > 0:
        spec.IAM1_5_norm_masked[spec.idx_solar] = IAM1_5_norm_full[spec.idx_solar]
    if spec.idx_thermal.size > 0:
        spec.I_bb_norm_masked[spec.idx_thermal] = I_bb_norm_full[spec.idx_thermal]

    print("--- [测试] 自定义范围已应用。 ---")


# -----------------------------------------------------------------
# 3. 模拟 TMM 计算 (获取吸收光谱)
# -----------------------------------------------------------------
def get_sample_absorptance(
        mat_manager: MaterialManager,
        spec_manager: SpectralDataManager
) -> Tuple[np.ndarray, str]:
    """
    为 tmm_simulator_widget.py 中的默认结构计算 TMM
    (PMMA 1068 / SiO2 6749 / TiO2 4675 / Ag 200 / Si)
    """
    print("--- [测试] 正在计算 TMM 默认结构的光谱... ---")

    # 1. 结构定义
    materials_input = ['PMMA', 'SiO2', 'TiO2']
    thickness_m = np.array([1068, 6749, 4675]) * 1e-9
    reflector_name = "Ag"
    reflector_d_m = 200 * 1e-9
    substrate_name = "Si"
    structure_str = "PMMA(1068nm) / SiO2(6749nm) / TiO2(4675nm) / Ag(200nm) / Si"

    # 2. 准备插值
    materials_to_load = materials_input + [reflector_name, substrate_name]
    interpolated_stack = mat_manager.get_interpolated_stack(
        materials_to_load,
        LAMBDA_GRID_UM,
        interp_method='pchip'
    )

    # 3. 组装层堆栈
    layer_stack_def = []
    for i in range(len(materials_input)):
        layer_stack_def.append({'n': interpolated_stack[materials_input[i]], 'd': thickness_m[i]})

    layer_stack_def.append({'n': interpolated_stack[reflector_name], 'd': reflector_d_m})
    layer_stack_def.append({'n': interpolated_stack[substrate_name], 'd': np.inf})

    # 4. 运行 TMM (0 度角)
    R_s, R_p = calculate_TMM_core(
        layer_stack_def,
        spec_manager.lambda_m,
        theta0_deg=0.0
    )

    # 5. 计算平均吸收率 (E_avg = 1 - R_avg)
    R_avg = (R_s + R_p) / 2.0
    E_avg = 1.0 - R_avg

    print("--- [测试] TMM 吸收光谱计算完毕。 ---")
    return E_avg, structure_str


# -----------------------------------------------------------------
# 4. 主执行函数
# -----------------------------------------------------------------
def main_test():
    ### --- 修改这里的参数 --- ###

    # 默认值: (0.3, 2.5)
    SOLAR_MIN_UM = 0
    SOLAR_MAX_UM =float('inf')

    # 默认值: (8.0, 13.0)
    THERMAL_MIN_UM = 0
    THERMAL_MAX_UM = float('inf')

    # 环境参数
    T_AMB = 300.0  # 环境温度 (K)
    HC_VALUE = 3.0  # 非辐射热交换系数 (W/m^2K)

    ### ------------------------- ###

    print("--- (测试程序) 正在启动... ---")

    # 1. 加载管理器
    mat_manager = MaterialManager()
    mat_manager.load_all_materials()
    spec_manager = SpectralDataManager()

    # 2. [关键] 应用自定义积分范围
    set_custom_integration_limits(
        spec_manager,
        SOLAR_MIN_UM, SOLAR_MAX_UM,
        THERMAL_MIN_UM, THERMAL_MAX_UM
    )

    # 3. 获取 TMM 光谱
    try:
        absorptance_spectrum, struct_str = get_sample_absorptance(mat_manager, spec_manager)
        print(f"  > 测试结构: {struct_str}")
    except Exception as e:
        print(f"\n*** TMM 计算失败: {e} ***")
        print("  > 请检查 'materials' 目录中是否包含 PMMA, SiO2, TiO2, Ag, Si？")
        return

    # 4. 运行冷却功率计算 (使用修改后的 spec_manager)
    print("\n--- [测试] 开始计算 P_sum (太阳吸收)... ---")
    try:
        P_sum = cooling_calc.calculate_P_sum(absorptance_spectrum, spec_manager)
        print(f"  > P_sum = {P_sum:.6f} W/m^2")
    except Exception as e:
        print(f"*** P_sum 计算失败: {e} ***")
        return

    print("\n--- [测试] 开始计算 P_atm (大气吸收)... ---")
    print("  > (这可能需要 1-2 分钟, 因为 dblquad 很慢)...")
    try:
        P_atm = cooling_calc.calculate_P_atm(T_AMB, absorptance_spectrum, spec_manager)
        print(f"  > P_atm = {P_atm:.6f} W/m^2")
    except Exception as e:
        print(f"*** P_atm 计算失败: {e} ***")
        return

    print(f"\n--- [测试] 开始计算 T_eq (平衡温度) @ hc = {HC_VALUE} ... ---")
    try:
        T_eq, T_drop = cooling_calc.find_equilibrium_temp(
            HC_VALUE,
            T_AMB,
            P_atm,  # 使用我们刚算出的 P_atm
            P_sum,  # 使用我们刚算出的 P_sum
            absorptance_spectrum,
            spec_manager  # 使用我们修改过的 spec_manager
        )

        if np.isnan(T_eq):
            print("  > 寻根失败 (在 200K-350K 范围内未找到平衡点)。")
        else:
            print(f"  > T_eq = {T_eq:.4f} K")
            print(f"  > T_drop (T_amb - T_eq) = {T_drop:.4f} K")

            # 5. [验证] 检查 T_eq 处的功率平衡
            print("\n--- [测试] 正在验证 T_eq 处的功率平衡... ---")
            P_rad_at_Teq = cooling_calc.calculate_P_rad(T_eq, absorptance_spectrum, spec_manager)
            P_non_at_Teq = cooling_calc.calculate_P_non(T_eq, T_AMB, HC_VALUE)

            P_out = P_rad_at_Teq + P_non_at_Teq
            P_in = P_atm + P_sum
            P_cool_check = P_out - P_in  # (Pcool = Prad + Pnon - Patm - Psum), Pnon 是负的

            # Pcool = Prad - Patm - Psum - Pnon(T_sample, T_amb, hc)
            # Pnon(T_sample, T_amb, hc) = hc * (T_amb - T_sample)
            # Pcool = Prad - Patm - Psum - hc * (T_amb - T_sample)
            # T_eq 时, T_sample = T_eq
            # P_rad_at_Teq - P_atm - P_sum = hc * (T_amb - T_eq)
            # P_rad_at_Teq - P_atm - P_sum = - (hc * (T_eq - T_amb))
            # P_rad_at_Teq - P_atm - P_sum = - P_non_at_Teq (因为 P_non = hc * (Tamb - Tsample))
            # P_rad_at_Teq + P_non_at_Teq = P_atm + P_sum

            print(f"  > P_rad (在 T_eq) = {P_rad_at_Teq:.6f} W/m^2")
            print(f"  > P_non (在 T_eq) = {P_non_at_Teq:.6f} W/m^2")
            print(f"  > P_atm (T_amb={T_AMB}K) = {P_atm:.6f} W/m^2")
            print(f"  > P_sum = {P_sum:.6f} W/m^2")
            print("  ---------------------------------")
            print(f"  > P_out (Prad + Pnon) = {P_out:.6f} W/m^2")
            print(f"  > P_in  (Patm + Psum) = {P_in:.6f} W/m^2")
            print(f"  > 平衡差异 (P_out - P_in) = {P_out - P_in:.8f} (应接近 0)")

    except Exception as e:
        print(f"*** T_eq 寻根失败: {e} ***")
        return

    print("\n--- [测试] 程序执行完毕。 ---")


if __name__ == "__main__":
    main_test()