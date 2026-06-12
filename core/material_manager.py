import os
import glob
import numpy as np
from scipy.interpolate import interp1d
import shutil
from typing import Union, Tuple, List

from core.constants import MATERIALS_DIR


class MaterialManager:
    """
    此类在 App 启动时加载一次所有原始 .txt 材料数据。
    然后, 它可以根据请求, 实时提供插值后的复折射率。
    """

    def __init__(self, materials_dir=MATERIALS_DIR):
        self.materials_dir = materials_dir
        self.raw_data_cache = {}
        self.available_materials = []
        print(f"材料管理器已初始化。路径: {self.materials_dir}")

    @staticmethod
    def _parse_material_file(filepath: str) -> Union[tuple, None]:
        """
        [V32 重构]
        解析单个 .txt 文件并返回可缓存的数据。
        返回 (mat_name, w_unique, n_unique, k_unique) 或 None
        """
        filename = os.path.basename(filepath)
        mat_name = os.path.splitext(filename)[0]

        try:
            data = np.genfromtxt(filepath, comments='#')
            if data.size == 0:
                print(f"  > 跳过 (空文件): {filename}")
                return None
            if data.ndim == 1:
                data = data.reshape(1, -1)

            num_columns = data.shape[1]
            if num_columns < 2:
                print(f"  > 跳过 (列数不足 < 2): {filename}")
                return None

            wavelengths_um_raw = data[:, 0]
            n_real_raw = data[:, 1]

            if num_columns >= 3:
                n_imag_raw = data[:, 2]
            else:
                n_imag_raw = np.zeros_like(wavelengths_um_raw)

        except Exception as e:
            print(f"  > 错误: 读取 {filename} 失败: {e}")
            return None

        wavelengths_um_unique, idx_unique = np.unique(wavelengths_um_raw, return_index=True)
        n_real_unique = n_real_raw[idx_unique]
        n_imag_unique = n_imag_raw[idx_unique]

        if len(wavelengths_um_unique) < 2:
            print(f"  > 跳过 (数据点不足): {filename}")
            return None

        return mat_name, wavelengths_um_unique, n_real_unique, n_imag_unique

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
            parsed_data = MaterialManager._parse_material_file(filepath)

            if parsed_data:
                mat_name, w, n, k = parsed_data
                self.raw_data_cache[mat_name] = (w, n, k)
                self.available_materials.append(mat_name)

        self.available_materials.sort()
        print(f"--- 成功加载 {len(self.available_materials)} 种材料 ---")
        return self.available_materials

    def add_new_material_from_file(self, source_filepath: str) -> Tuple[str, List]:
        """
        [V32 新增]
        从用户选择的路径复制 .txt 文件到 materials 目录,
        然后加载它到缓存, 并更新可用列表。

        返回: (new_material_name, full_material_list)
        """
        print(f"--- (Manager) 正在尝试添加新材料: {source_filepath} ---")

        # 1. 检查目标文件是否已存在
        filename = os.path.basename(source_filepath)
        mat_name = os.path.splitext(filename)[0]

        if mat_name in self.available_materials:
            raise ValueError(f"添加失败: 材料 '{mat_name}' 已存在于数据库中。")

        dest_filepath = os.path.join(self.materials_dir, filename)

        if os.path.exists(dest_filepath):
            raise ValueError(f"添加失败: 文件 '{filename}' 已存在于 materials 目录中。")

        # 2. 复制文件到 materials 目录
        try:
            shutil.copy(source_filepath, dest_filepath)
            print(f"  > 文件已复制到: {dest_filepath}")
        except Exception as e:
            raise IOError(f"复制文件失败: {e}")

        # 3. 解析新文件
        parsed_data = MaterialManager._parse_material_file(dest_filepath)

        if parsed_data is None:
            # 解析失败, 尝试删除复制过来的坏文件
            try:
                os.remove(dest_filepath)
            except Exception as e:
                print(f"*** 警告: 无法删除无效的材料文件: {e} ***")
            raise ValueError("添加失败: 文件格式无效 (如: 列数 < 2 或数据点 < 2)。")

        # 4. (成功) 更新缓存和列表
        mat_name, w, n, k = parsed_data
        self.raw_data_cache[mat_name] = (w, n, k)
        self.available_materials.append(mat_name)
        self.available_materials.sort()

        print(f"--- 成功添加新材料: {mat_name} ---")

        # 5. 返回新状态
        return mat_name, self.available_materials

    @staticmethod
    def _interpolate_single_material(w_raw, n_raw, k_raw, lambda_um_grid, kind):
        """
        对单个材料执行插值和外推。
        """
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

        n_complex_column = (n_real_interp + 1j * np.abs(n_imag_interp)).reshape(-1, 1)
        return n_complex_column

    def get_interpolated_stack(self, material_names, lambda_um_grid, interp_method='pchip'):
        """
        (在点击“计算”时运行)
        根据请求, 实时插值所需的材料。
        """
        interpolated_stack = {}
        kind_map = {'pchip': 'cubic', 'linear': 'linear', 'spline': 'slinear'}
        kind = kind_map.get(interp_method, 'cubic')

        for mat_name in material_names:
            if mat_name not in self.raw_data_cache:
                valid_mats = ", ".join(self.available_materials)
                raise ValueError(f"错误: 材料 '{mat_name}' 未在缓存中找到。\n可用材料: {valid_mats}")

            w_raw, n_raw, k_raw = self.raw_data_cache[mat_name]

            n_complex_column = MaterialManager._interpolate_single_material(
                w_raw, n_raw, k_raw, lambda_um_grid, kind
            )

            interpolated_stack[mat_name] = n_complex_column

        return interpolated_stack