import os
import glob
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

# -----------------------------------------------------------------
# 1. Matplotlib 字体设置 (解决中文乱码)
# -----------------------------------------------------------------
# (请确保您的系统上有 'SimHei' 字体, 或者换成 'Microsoft YaHei' 等)
plt.rcParams['font.sans-serif'] = ['SimHei']  # 设置中文字体
plt.rcParams['axes.unicode_minus'] = False  # 修复负号显示问题

# -----------------------------------------------------------------
# 2. 定义常量和路径
# -----------------------------------------------------------------
N_POINTS = 1000  # 标准波长网格的采样点数
LAMBDA_MIN_UM = 0.3  # 标准网格起始波长 (μm)
LAMBDA_MAX_UM = 14.0  # 标准网格终止波长 (μm)

# 获取当前脚本所在的文件夹路径
BASE_DIR = os.path.dirname(__file__)
MATERIALS_DIR = os.path.join(BASE_DIR, 'materials')

# [新] 为预览图创建一个新文件夹
PREVIEW_DIR = os.path.join(BASE_DIR, '_material_previews')
if not os.path.exists(PREVIEW_DIR):
    os.makedirs(PREVIEW_DIR)  # 自动创建文件夹


# -----------------------------------------------------------------
# 3. 粘贴 MaterialManager 类 (与 constants.py 相同)
# -----------------------------------------------------------------
class MaterialManager:
    """
    此类在 App 启动时加载一次所有原始 .txt 材料数据。
    然后, 它可以根据请求, 实时提供插值后的复折射率。
    """

    def __init__(self, materials_dir):
        self.materials_dir = materials_dir
        self.raw_data_cache = {}
        self.available_materials = []
        print(f"材料管理器已初始化。路径: {self.materials_dir}")

    def load_all_materials(self):
        """
        (在 App 启动时运行一次)
        扫描 data_dir, 加载所有 .txt 文件到 raw_data_cache。
        """
        print("--- 正在加载所有原始材料 .txt 文件... ---")

        file_list = glob.glob(os.path.join(self.materials_dir, '*.txt'))

        if not file_list:
            print(f"*** 警告: 在 {self.materials_dir} 中未找到任何 .txt 文件 ***")
            return []

        for filepath in file_list:
            filename = os.path.basename(filepath)
            mat_name = os.path.splitext(filename)[0]

            try:
                data = np.loadtxt(filepath)
                if data.size == 0:
                    print(f"  > 跳过 (空文件): {filename}")
                    continue
                if data.ndim == 1:
                    data = data.reshape(1, -1)

                num_columns = data.shape[1]
                wavelengths_um_raw = data[:, 0]
                n_real_raw = data[:, 1]

                if num_columns >= 3:
                    n_imag_raw = data[:, 2]
                else:
                    n_imag_raw = np.zeros_like(wavelengths_um_raw)

            except Exception as e:
                print(f"  > 错误: 读取 {filename} 失败: {e}")
                continue

            wavelengths_um_unique, idx_unique = np.unique(wavelengths_um_raw, return_index=True)
            n_real_unique = n_real_raw[idx_unique]
            n_imag_unique = n_imag_raw[idx_unique]

            if len(wavelengths_um_unique) < 2:
                print(f"  > 跳过 (数据点不足): {filename}")
                continue

            self.raw_data_cache[mat_name] = (wavelengths_um_unique, n_real_unique, n_imag_unique)
            self.available_materials.append(mat_name)

        self.available_materials.sort()
        print(f"--- 成功加载 {len(self.available_materials)} 种材料 ---")
        return self.available_materials

    def get_interpolated_material(self, mat_name, lambda_um_grid, interp_method='pchip'):
        """
        实时插值 *单一* 材料。
        """
        kind_map = {'pchip': 'cubic', 'linear': 'linear', 'spline': 'slinear'}
        kind = kind_map.get(interp_method, 'cubic')

        if mat_name not in self.raw_data_cache:
            raise ValueError(f"错误: 材料 '{mat_name}' 未在原始数据缓存中找到。")

        w_raw, n_raw, k_raw = self.raw_data_cache[mat_name]

        interp_func_n = interp1d(w_raw, n_raw, kind=kind, bounds_error=False, fill_value=np.nan)
        interp_func_k = interp1d(w_raw, k_raw, kind=kind, bounds_error=False, fill_value=np.nan)

        n_real_interp = interp_func_n(lambda_um_grid)
        n_imag_interp = interp_func_k(lambda_um_grid)

        extrap_func_n = interp1d(w_raw, n_raw, kind='nearest', fill_value="extrapolate")
        extrap_func_k = interp1d(w_raw, k_raw, kind='nearest', fill_value="extrapolate")

        nan_indices = np.isnan(n_real_interp)
        if np.any(nan_indices):
            n_real_interp[nan_indices] = extrap_func_n(lambda_um_grid[nan_indices])
            n_imag_interp[nan_indices] = extrap_func_k(lambda_um_grid[nan_indices])

        n_complex = n_real_interp + 1j * np.abs(n_imag_interp)

        # 返回插值结果 和 原始数据 (用于绘图)
        return n_complex, (w_raw, n_raw, k_raw)


# -----------------------------------------------------------------
# 步骤 4: 主函数 (运行可视化)
# -----------------------------------------------------------------
if __name__ == "__main__":

    print("--- 开始运行材料可视化脚本 ---")

    # --- 1. 初始化 ---
    material_manager = MaterialManager(MATERIALS_DIR)
    available_mats = material_manager.load_all_materials()

    # --- 2. 创建标准波长网格 ---
    lambda_grid_um = np.linspace(LAMBDA_MIN_UM, LAMBDA_MAX_UM, N_POINTS)

    print(f"\n--- 正在为 {len(available_mats)} 种材料生成预览图... ---")

    # --- 3. 循环, 插值, 并绘图 ---
    for mat_name in available_mats:
        try:
            # 3a. 获取插值后的数据, 以及原始数据
            n_complex_interp, (w_raw, n_raw, k_raw) = material_manager.get_interpolated_material(
                mat_name,
                lambda_grid_um,
                interp_method='pchip'  # 您可以在这里改为 'linear' 测试
            )

            # 3b. 绘图
            plt.figure(figsize=(10, 6))  # 创建一个新图窗

            # 绘制 n
            plt.plot(w_raw, n_raw, 'bo', markersize=3, alpha=0.5, label='原始 n')
            plt.plot(lambda_grid_um, n_complex_interp.real, 'b-', linewidth=1.5, label='插值 n (pchip+nearest)')

            # 绘制 k (如果它有值)
            if np.any(k_raw != 0):
                plt.plot(w_raw, k_raw, 'ro', markersize=3, alpha=0.5, label='原始 k')
                plt.plot(lambda_grid_um, n_complex_interp.imag, 'r-', linewidth=1.5, label='插值 k (pchip+nearest)')

            plt.xlabel('波长 (μm)')
            plt.ylabel('n, k')
            plt.title(f'{mat_name} 复折射率插值对比')
            plt.legend()
            plt.grid(True)
            plt.xlim(LAMBDA_MIN_UM, LAMBDA_MAX_UM)  # 固定 X 轴范围

            # 3c. 保存 PNG 文件
            save_path = os.path.join(PREVIEW_DIR, f'{mat_name}_preview.png')
            plt.savefig(save_path)
            plt.close()  # 关闭图窗, 否则会占用大量内存

            print(f"  > 已保存: {mat_name}_preview.png")

        except Exception as e:
            print(f"  > 错误: 无法处理 {mat_name}: {e}")

    print(f"\n--- 可视化完成! 所有预览图已保存到: {PREVIEW_DIR} ---")