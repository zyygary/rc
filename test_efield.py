# -----------------------------------------------------------------
# test_efield_v52.py (V52 - 交互式 2D 电场热力图)
# 描述:
# 1. [V52 重构] 这是一个完整的 PyQt 应用程序 (结合了 V50 和 V51)
# 2. [V52 新增] 添加一个滑块来控制 'MgF2' 层的厚度
# 3. [V52 重构] 绘图区域是一个 2D 热力图 (波长 vs 深度)
# 4. [V52 修正] 滑块的 'sliderReleased' (释放时) 信号连接到
#    'update_2d_heatmap', 触发 *完整* 的 2D 扫描
# 5. (V50 逻辑) Y 轴 (深度) 被反转 (invertY)
# 6. (V49 逻辑) 颜色条使用 "蓝-黄-红"
# 7. (V34 依赖) 依赖 V34 的 material_manager 来处理 SiN/Si3N4
# -----------------------------------------------------------------

import sys
import numpy as np
import pyqtgraph as pg

# [V51] 导入 PySide2 控件
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QSlider, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
)
# [V51 修正] 导入 Qt
from PySide2.QtCore import Qt, QRectF
from typing import List, Dict, Any, Tuple

# [V47] 导入现有的 MaterialManager
# (此脚本依赖 V34 版本的 material_manager.py 来处理 SiN/Si3N4)
from core.material_manager import MaterialManager
from core.constants import MATERIALS_DIR


# -----------------------------------------------------------------
# V48 TMM 电场计算核心 (S-偏振)
# (与 V50 版本的函数完全相同)
# -----------------------------------------------------------------

def calculate_TMM_efield_s_pol(
        layer_stack: List[Dict[str, Any]],
        lambda_m: float,
        theta0_deg: float,
        z_grid_m: np.ndarray
) -> np.ndarray:
    k0 = 2 * np.pi / lambda_m
    theta0_rad = np.deg2rad(theta0_deg)

    # --- 1. 初始化 (空气) ---
    n_air = 1.0 + 0j
    cos_theta_air = np.cos(theta0_rad)
    eta_air = n_air * cos_theta_air

    # --- 2. [前向传播] 计算总传输矩阵 (M_total) ---
    M_total = np.array([[1, 0], [0, 1]], dtype=complex)
    interfaces = []
    n_current = n_air
    cos_theta_current = cos_theta_air

    for layer in layer_stack:
        n_next = layer['n']
        d_m = layer['d']

        sin_theta_next = n_current * np.sin(np.arccos(cos_theta_current)) / n_next
        cos_theta_next = np.lib.scimath.sqrt(1.0 - sin_theta_next ** 2)
        eta_next = n_next * cos_theta_next

        if d_m == np.inf:
            interfaces.append({
                'n': n_next, 'cos_theta': cos_theta_next, 'eta': eta_next,
                'd_m': d_m, 'M_layer': np.array([[1, 0], [0, 1]], dtype=complex)
            })
            break

        delta = k0 * n_next * cos_theta_next * d_m
        cos_delta = np.cos(delta)
        sin_delta = np.sin(delta)

        M_layer = np.array([
            [cos_delta, (1j / eta_next) * sin_delta],
            [1j * eta_next * sin_delta, cos_delta]
        ], dtype=complex)

        M_total = M_total.dot(M_layer)

        interfaces.append({
            'n': n_next, 'cos_theta': cos_theta_next, 'eta': eta_next,
            'd_m': d_m, 'M_layer': M_layer
        })

        n_current = n_next
        cos_theta_current = cos_theta_next

    # --- 3. 计算 反射/透射 系数 (r, t) ---
    eta_sub = interfaces[-1]['eta']
    M11 = M_total[0, 0];
    M12 = M_total[0, 1]
    M21 = M_total[1, 0];
    M22 = M_total[1, 1]

    num_r = (eta_air * M11 + eta_air * eta_sub * M12) - (M21 + eta_sub * M22)
    den_r = (eta_air * M11 + eta_air * eta_sub * M12) + (M21 + eta_sub * M22)
    r_s = num_r / den_r
    t_s = (1 + r_s) / (M11 + M12 * eta_sub)

    # --- 4. [反向传播] 重构电场 ---
    E_profile = np.zeros(z_grid_m.shape, dtype=complex)

    # 4b. 在空气中 (z < 0)
    kz_air = k0 * n_air * cos_theta_air
    idx_air = (z_grid_m < 0)
    E_profile[idx_air] = (
            np.exp(1j * kz_air * z_grid_m[idx_air]) +
            r_s * np.exp(-1j * kz_air * z_grid_m[idx_air])
    )

    # 4c. [核心] 在层中和基底中 (z >= 0)
    E_current = t_s
    H_current = eta_sub * t_s

    for i in range(len(interfaces) - 1, -1, -1):
        layer = interfaces[i]
        n_j = layer['n']
        d_j = layer['d_m']
        cos_j = layer['cos_theta']
        eta_j = layer['eta']
        M_j = layer['M_layer']

        z_start_m = 0.0
        for k in range(i):
            z_start_m += interfaces[k]['d_m']

        if d_j == np.inf:
            z_end_m = z_grid_m[-1]
        else:
            z_end_m = z_start_m + d_j

        idx_layer = (z_grid_m >= (z_start_m - 1e-12)) & (z_grid_m <= (z_end_m + 1e-12))

        z_prime = z_grid_m[idx_layer] - z_start_m
        kz_j = k0 * n_j * cos_j

        if d_j == np.inf:
            E_profile[idx_layer] = E_current * np.exp(1j * kz_j * z_prime)
        else:
            z_rev = z_end_m - z_grid_m[idx_layer]
            kz_j_rev = k0 * n_j * cos_j

            E_profile[idx_layer] = (
                    E_current * np.cos(kz_j_rev * z_rev) +
                    (1j * H_current / eta_j) * np.sin(kz_j_rev * z_rev)
            )

        if d_j != np.inf:
            E_left = M_j[0, 0] * E_current + M_j[0, 1] * H_current
            H_left = M_j[1, 0] * E_current + M_j[1, 1] * H_current
            E_current, H_current = E_left, H_left

    return np.abs(E_profile) ** 2


# -----------------------------------------------------------------
# V52 [重构] 主 GUI 窗口
# -----------------------------------------------------------------
class TestEfieldWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # --- 1. 定义常量 ---

        # [V51] 使用您提供的新结构
        self.STRUCTURE = [
            {'mat': 'Si3N4', 'd_nm': 150},
            {'mat': 'MgF2', 'd_nm': 4000},  # <--- 这是我们将扫描的层
            {'mat': 'SiN', 'd_nm': 5606},
            {'mat': 'Ag', 'd_nm': 200},
            {'mat': 'Si', 'd_nm': np.inf},
        ]

        # [V51] MgF2 滑块的范围 (nm)
        self.MGF2_MIN_NM = 0
        self.MGF2_MAX_NM = 8000
        self.MGF2_START_NM = 4000

        # [V50] Z 轴范围 (nm)
        self.Z_START_NM = -500
        self.Z_STOP_NM = 15000  # 150 + 8000(max) + 5606 + 200 + ...
        self.Z_POINTS = 500

        # [V50] X 轴: 波长 λ 轴 (您要求的 8-13 um)
        self.LAMBDA_START_UM = 8.0
        self.LAMBDA_STOP_UM = 13.0
        self.LAMBDA_POINTS = 100

        # --- 2. 准备数据 ---
        self.z_grid_nm = np.linspace(self.Z_START_NM, self.Z_STOP_NM, self.Z_POINTS)
        self.z_grid_m = self.z_grid_nm * 1e-9
        self.lambda_grid_um = np.linspace(self.LAMBDA_START_UM, self.LAMBDA_STOP_UM, self.LAMBDA_POINTS)
        self.lambda_grid_m = self.lambda_grid_um * 1e-6

        # [V52] 存储层边界线
        self.boundary_lines = []

        try:
            self.load_materials()
        except Exception as e:
            print(f"!!! 加载材料失败: {e}")
            print("!!! 请确保您已更新 core/material_manager.py (V34) 以修复 SiN/Si3N4 Bug")
            sys.exit()

        # --- 3. 构建 UI ---
        self.setup_ui()

        # --- 4. 运行第一次计算 ---
        self.update_2d_heatmap()

    def load_materials(self):
        """[V52] 在 *整个* 波长范围上加载所有材料"""
        print(f"--- (Test V52) 正在加载材料 @ {self.LAMBDA_START_UM}-{self.LAMBDA_STOP_UM} um... ---")
        mat_manager = MaterialManager(materials_dir=MATERIALS_DIR)
        mat_manager.load_all_materials()

        materials_to_load = [layer['mat'] for layer in self.STRUCTURE]

        # [V52] 在 *整个* 波长网格上插值 *一次*
        self.interpolated_stack = mat_manager.get_interpolated_stack(
            materials_to_load,
            self.lambda_grid_um,
            interp_method='pchip'
        )
        print("--- (Test V52) 材料加载完毕 ---")

    def setup_ui(self):
        """[V52] 构建 GUI 界面 (滑块 + 2D 热力图)"""
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)

        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # 1. 滑块布局
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel(f"MgF2 厚度 (nm) [{self.MGF2_MIN_NM} - {self.MGF2_MAX_NM}]:"))

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(self.MGF2_MIN_NM, self.MGF2_MAX_NM)
        self.slider.setValue(self.MGF2_START_NM)

        self.lbl_slider = QLabel(f"{self.MGF2_START_NM} nm")
        self.lbl_slider.setMinimumWidth(60)

        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.lbl_slider)

        # 2. [V52] 2D 绘图控件 (V50 逻辑)
        plot_layout = QGridLayout()

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.invertY(True)  # [V50] Y 轴反转 (Z=0 在顶部)

        self.image_item = pg.ImageItem()
        self.plot_widget.addItem(self.image_item)

        self.hist_lut = pg.HistogramLUTWidget()
        self.hist_lut.setImageItem(self.image_item)
        self.hist_lut.setMaximumWidth(150)

        # [V50/V49 修正] 设置 "蓝-黄-红" 颜色条
        pos = [0.0, 0.5, 1.0]
        colors = [
            (0, 0, 255, 255),  # 蓝
            (255, 255, 0, 255),  # 黄
            (255, 0, 0, 255)  # 红
        ]
        cmap = pg.ColorMap(pos, colors)
        self.hist_lut.gradient.setColorMap(cmap)

        plot_layout.addWidget(self.plot_widget, 0, 0)  # (row, col)
        plot_layout.addWidget(self.hist_lut, 0, 1)  # (row, col)

        # 3. 组合布局
        main_layout.addLayout(slider_layout)
        main_layout.addLayout(plot_layout)
        self.setCentralWidget(central_widget)

        # 4. 连接信号
        # [V52] 仅在滑块释放时触发
        self.slider.sliderReleased.connect(self.update_2d_heatmap)
        # [V52] 拖动时仅更新标签
        self.slider.valueChanged.connect(lambda val: self.lbl_slider.setText(f"{val} nm"))

        self.setWindowTitle(f"TMM 2D 交互式电场 (V52)")
        self.setGeometry(100, 100, 1000, 700)

    def update_2d_heatmap(self):
        """
        [V52] 核心: 当滑块 *释放* 时被调用
        重新计算 *整个* 2D 热力图
        """

        # 1. 获取滑块值
        d_mgf2_nm = self.slider.value()
        self.lbl_slider.setText(f"{d_mgf2_nm} nm")

        print(f"--- (Test V52) 开始 2D 扫描, MgF2 = {d_mgf2_nm} nm ... ---")
        self.plot_widget.setTitle(f"正在计算 (MgF2 = {d_mgf2_nm} nm)...")
        QApplication.processEvents()  # 刷新 UI

        # 2. 初始化输出矩阵: (行=Z, 列=λ)
        efield_matrix = np.zeros((self.Z_POINTS, self.LAMBDA_POINTS))

        # 3. [V52] 循环遍历波长
        for i, (lambda_um, lambda_m) in enumerate(zip(self.lambda_grid_um, self.lambda_grid_m)):

            # 3a. 构建此单一波长下的层堆栈
            layer_stack_input = []

            # (L1: Si3N4)
            n_si3n4 = self.interpolated_stack['Si3N4'][i].item()
            layer_stack_input.append({'n': n_si3n4, 'd': 150e-9})

            # (L2: MgF2) - 使用滑块值
            n_mgf2 = self.interpolated_stack['MgF2'][i].item()
            layer_stack_input.append({'n': n_mgf2, 'd': d_mgf2_nm * 1e-9})

            # (L3: SiN)
            n_sin = self.interpolated_stack['SiN'][i].item()
            layer_stack_input.append({'n': n_sin, 'd': 5606e-9})

            # (L4: Ag)
            n_ag = self.interpolated_stack['Ag'][i].item()
            layer_stack_input.append({'n': n_ag, 'd': 200e-9})

            # (L5: Si)
            n_si = self.interpolated_stack['Si'][i].item()
            layer_stack_input.append({'n': n_si, 'd': np.inf})

            # 3b. 运行 TMM
            try:
                E_field_sq = calculate_TMM_efield_s_pol(
                    layer_stack_input,
                    lambda_m,
                    theta0_deg=0,
                    z_grid_m=self.z_grid_m
                )
                efield_matrix[:, i] = E_field_sq
            except Exception as e:
                print(f"!!! TMM 计算失败 @ {lambda_um}um: {e}")
                efield_matrix[:, i] = np.nan

        print("--- (Test V52) 2D 扫描完毕 ---")

        # 4. [V52] 更新热力图

        # 4a. 清除旧的边界线
        for line in self.boundary_lines:
            self.plot_widget.removeItem(line)
        self.boundary_lines.clear()

        # 4b. 设置图像数据 (转置)
        image_data_to_plot = efield_matrix.T
        self.image_item.setImage(image_data_to_plot)

        # 4c. 设置坐标轴
        x_min = self.lambda_grid_um[0]
        x_max = self.lambda_grid_um[-1]
        y_min = self.z_grid_nm[0]
        y_max = self.z_grid_nm[-1]
        rect = QRectF(x_min, y_min, x_max - x_min, y_max - y_min)
        self.image_item.setRect(rect)

        # 4d. 设置色阶
        min_val = np.nanmin(image_data_to_plot)
        max_val = np.nanmax(image_data_to_plot)
        self.hist_lut.setLevels(min_val, max_val)
        self.hist_lut.autoHistogramRange()

        # 4e. 绘制 *动态* 边界
        z_l1 = 150.0
        z_l2 = z_l1 + d_mgf2_nm  # <--- 动态
        z_l3 = z_l2 + 5606.0
        z_l4 = z_l3 + 200.0

        for z in [z_l1, z_l2, z_l3, z_l4]:
            h_line = pg.InfiniteLine(pos=z, angle=0, movable=False,
                                     pen=pg.mkPen('k', style=Qt.DashLine))
            self.plot_widget.addItem(h_line)
            self.boundary_lines.append(h_line)

        self.plot_widget.setTitle(f"总电场 |E|^2 (法向入射), MgF2 = {d_mgf2_nm} nm")
        self.plot_widget.setLabel('bottom', f"波长 (μm) [{self.LAMBDA_START_UM} - {self.LAMBDA_STOP_UM}]")
        self.plot_widget.setLabel('left', "深度 Z (nm) [Z=0 为表面]")

        # (我们不需要 autoRange, 因为 Z 和 Lambda 范围是固定的)
        # self.plot_widget.autoRange()


# -----------------------------------------------------------------
# V52 [新增] 启动 App
# -----------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestEfieldWindow()
    window.show()
    sys.exit(app.exec_())