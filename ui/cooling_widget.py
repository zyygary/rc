from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import core.cooling_calculator as cooling_calc
from core.material_manager import MaterialManager
from core.spectral_manager import SpectralDataManager
from core.tmm_core import calculate_TMM_core
from ui.i18n import normalize_language, tr
from ui.tmm_simulator_widget import TmmSimulatorWidget


class CoolingWidget(QWidget):
    last_absorptance: Optional[np.ndarray] = None
    last_P_atm: Optional[float] = None
    last_P_sum: Optional[float] = None
    last_T_amb: Optional[float] = None

    def __init__(
        self,
        material_manager: MaterialManager,
        spectral_manager: SpectralDataManager,
        tmm_simulator: TmmSimulatorWidget,
        parent=None,
        language="zh",
    ):
        super().__init__(parent)
        self.language = normalize_language(language)
        self.material_manager = material_manager
        self.spectral_manager = spectral_manager
        self.tmm_sim = tmm_simulator
        self.lambda_grid_um = self.spectral_manager.lambda_um
        self.loaded_structure_text = ""
        self.setup_ui()
        self.set_language(self.language)

    def tr(self, zh_text: str, en_text: str) -> str:
        return tr(self.language, zh_text, en_text)

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        left_panel = QWidget()
        left_panel.setFixedWidth(380)
        left_layout = QVBoxLayout(left_panel)

        load_layout = QHBoxLayout()
        self.btn_load_structure = QPushButton()
        load_layout.addWidget(self.btn_load_structure)
        left_layout.addLayout(load_layout)
        self.lbl_loaded_structure = QLabel()
        self.lbl_loaded_structure.setWordWrap(True)
        self.lbl_loaded_structure.setStyleSheet("font-size: 9pt;")
        left_layout.addWidget(self.lbl_loaded_structure)

        self.params_group = QGroupBox()
        params_layout = QGridLayout()
        self.lbl_tamb = QLabel()
        params_layout.addWidget(self.lbl_tamb, 0, 0)
        self.edit_tamb = QLineEdit("300")
        params_layout.addWidget(self.edit_tamb, 0, 1, 1, 2)

        self.lbl_hc_values = QLabel()
        params_layout.addWidget(self.lbl_hc_values, 1, 0)
        self.edit_hc_values = QLineEdit("0, 3, 6, 12")
        params_layout.addWidget(self.edit_hc_values, 1, 1, 1, 2)

        self.lbl_tsample_range = QLabel()
        params_layout.addWidget(self.lbl_tsample_range, 2, 0)
        self.edit_tsample_min = QLineEdit("273")
        self.edit_tsample_max = QLineEdit("310")
        params_layout.addWidget(self.edit_tsample_min, 2, 1)
        params_layout.addWidget(self.edit_tsample_max, 2, 2)

        self.lbl_tsample_points = QLabel()
        params_layout.addWidget(self.lbl_tsample_points, 3, 0)
        self.edit_tsample_points = QLineEdit("100")
        params_layout.addWidget(self.edit_tsample_points, 3, 1, 1, 2)
        self.params_group.setLayout(params_layout)
        left_layout.addWidget(self.params_group)

        self.btn_run_cooling_calc = QPushButton()
        self.btn_run_cooling_calc.setObjectName("CalculateButton")
        left_layout.addWidget(self.btn_run_cooling_calc)

        self.eq_group = QGroupBox()
        eq_layout = QGridLayout()
        self.lbl_hc_eq = QLabel()
        eq_layout.addWidget(self.lbl_hc_eq, 0, 0)
        self.edit_hc_eq = QLineEdit("3")
        eq_layout.addWidget(self.edit_hc_eq, 0, 1)
        self.btn_calc_eq = QPushButton()
        eq_layout.addWidget(self.btn_calc_eq, 0, 2)

        self.lbl_eq_temp_result = QLabel()
        self.lbl_eq_temp_result.setStyleSheet("font-weight: bold;")
        eq_layout.addWidget(self.lbl_eq_temp_result, 1, 0, 1, 2)

        self.lbl_eq_drop_result = QLabel()
        self.lbl_eq_drop_result.setStyleSheet("font-weight: bold; color: #007BFF;")
        eq_layout.addWidget(self.lbl_eq_drop_result, 2, 0, 1, 3)
        self.eq_group.setLayout(eq_layout)
        left_layout.addWidget(self.eq_group)

        self.log_group = QGroupBox()
        log_layout = QGridLayout()
        self.lbl_log_psum = QLabel()
        self.lbl_log_patm = QLabel()
        self.lbl_log_prad = QLabel()
        self.lbl_log_pnon = QLabel()
        log_layout.addWidget(self.lbl_log_psum, 0, 0)
        log_layout.addWidget(self.lbl_log_patm, 1, 0)
        log_layout.addWidget(self.lbl_log_prad, 2, 0)
        log_layout.addWidget(self.lbl_log_pnon, 3, 0)
        self.log_group.setLayout(log_layout)
        left_layout.addWidget(self.log_group)
        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.plot_widget_pcool = pg.PlotWidget()
        self.plot_widget_pcool.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget_pcool.addLegend()
        right_layout.addWidget(self.plot_widget_pcool, 2)

        self.spec_group = QGroupBox()
        spec_layout = QHBoxLayout()
        self.plot_widget_solar = pg.PlotWidget()
        self.plot_widget_solar.setXRange(0.3, 2.5)
        self.plot_widget_solar.setYRange(0, 1)
        self.plot_widget_atm = pg.PlotWidget()
        self.plot_widget_atm.setYRange(0, 1)
        self.plot_widget_atm.setXRange(8, 13)
        spec_layout.addWidget(self.plot_widget_solar)
        spec_layout.addWidget(self.plot_widget_atm)
        self.spec_group.setLayout(spec_layout)
        right_layout.addWidget(self.spec_group, 1)
        main_layout.addWidget(right_panel, 1)

        self.btn_load_structure.clicked.connect(self.load_spectrum_from_tmm_tab)
        self.btn_run_cooling_calc.clicked.connect(self.run_cooling_calculation)
        self.btn_calc_eq.clicked.connect(self.on_calc_equilibrium)
        self.edit_hc_eq.returnPressed.connect(self.on_calc_equilibrium)

    def set_language(self, language):
        self.language = normalize_language(language)
        self.btn_load_structure.setText(self.tr("加载 TMM 光谱", "Load TMM Spectrum"))
        if self.loaded_structure_text:
            self.lbl_loaded_structure.setText(self.loaded_structure_text)
        else:
            self.lbl_loaded_structure.setText(self.tr("未加载光谱。请先加载光谱。", "No spectrum loaded. Please load a spectrum first."))
        self.params_group.setTitle(self.tr("P_cool 扫描参数", "P_cool Sweep Parameters"))
        self.lbl_tamb.setText(self.tr("环境温度 T_amb (K):", "Ambient Temperature T_amb (K):"))
        self.lbl_hc_values.setText(self.tr("hc 系数 (逗号分隔):", "hc Values (comma separated):"))
        self.lbl_tsample_range.setText(self.tr("T_sample 范围 (K):", "T_sample Range (K):"))
        self.lbl_tsample_points.setText(self.tr("扫描点数:", "Number of Points:"))
        self.btn_run_cooling_calc.setText(self.tr("计算 P_cool 扫描曲线", "Compute P_cool Sweep"))
        self.eq_group.setTitle(self.tr("平衡温度计算 (P_cool = 0)", "Equilibrium Temperature (P_cool = 0)"))
        self.lbl_hc_eq.setText(self.tr("选择 HC 系数:", "Select HC Value:"))
        self.btn_calc_eq.setText(self.tr("计算 T_eq", "Compute T_eq"))
        self.log_group.setTitle(self.tr("功率分析 (W/m^2)", "Power Analysis (W/m^2)"))
        self.spec_group.setTitle(self.tr("光谱特性分析 (0 deg, 平均)", "Spectral Analysis (0 deg, Average)"))
        self.plot_widget_pcool.setLabel("bottom", "T_sample (K)")
        self.plot_widget_pcool.setLabel("left", "P_cool (W/m^2)")
        self.plot_widget_solar.setLabel("bottom", self.tr("波长 (um)", "Wavelength (um)"))
        self.plot_widget_solar.setLabel("left", self.tr("吸收率 / 归一化强度", "Absorptance / Normalized Intensity"))
        self.plot_widget_atm.setLabel("bottom", self.tr("波长 (um)", "Wavelength (um)"))
        self._reset_result_labels()
        self.plot_widget_pcool.setTitle(self.tr("P_cool vs T_sample (未运行)", "P_cool vs T_sample (Not Run)"))
        if self.last_absorptance is not None:
            self.plot_spectral_analysis()

    def _reset_result_labels(self, hc_value_text: str = "--"):
        self.lbl_eq_temp_result.setText("T_eq = -- K")
        self.lbl_eq_drop_result.setText(self.tr("降温量 Delta T = -- K", "Delta T (Cooling) = -- K"))
        self.lbl_log_psum.setText(self.tr("P_sum (太阳吸收) = --", "P_sum (Solar Absorption) = --"))
        self.lbl_log_patm.setText(self.tr("P_atm (大气吸收) = --", "P_atm (Atmospheric Absorption) = --"))
        self.lbl_log_prad.setText("P_rad (T_eq) = --")
        self.lbl_log_pnon.setText(f"P_non (T_eq, hc={hc_value_text}) = --")

    def _show_equilibrium_unavailable(self, hc_value: float):
        self.lbl_eq_temp_result.setText("T_eq = N/A")
        self.lbl_eq_drop_result.setText(self.tr("降温量 Delta T = N/A", "Delta T (Cooling) = N/A"))
        self.lbl_log_prad.setText("P_rad (T_eq) = --")
        self.lbl_log_pnon.setText(f"P_non (T_eq, hc={hc_value:g}) = --")

    def load_spectrum_from_tmm_tab(self):
        self.last_absorptance = None
        self.last_P_atm = None
        self.last_P_sum = None
        self.last_T_amb = None
        self.plot_widget_pcool.clear()
        self.plot_widget_pcool.addLegend()
        self.plot_widget_pcool.setTitle(self.tr("P_cool vs T_sample (光谱已更新，请点击计算)", "P_cool vs T_sample (Spectrum Updated, Click Compute)"))
        self._reset_result_labels(self.edit_hc_eq.text() or "--")

        try:
            layers_widgets = self.tmm_sim.layer_widgets
            reflector_name = self.tmm_sim.combo_reflector.currentText()
            substrate_name = self.tmm_sim.combo_substrate.currentText()
            reflector_thick_nm = float(self.tmm_sim.edit_reflector_thick.text())

            if not layers_widgets:
                raise ValueError(self.tr("TMM 页面中没有功能层。", "There are no functional layers in the TMM tab."))

            base_structure_layers = []
            base_structure_str = ""
            for layer in layers_widgets:
                mat_name = layer.combo_material.currentText()
                thick_nm = float(layer.edit_thickness.text())
                base_structure_layers.append({"name": mat_name, "d_nm": thick_nm})
                base_structure_str += f"{mat_name}({thick_nm}nm) / "

            base_reflector = {"name": reflector_name, "d_nm": reflector_thick_nm}
            base_substrate = {"name": substrate_name, "d_nm": np.inf}
            base_structure_str += f"{reflector_name}({reflector_thick_nm}nm) / {substrate_name}"

            materials_to_load = [layer["name"] for layer in base_structure_layers]
            materials_to_load.extend([reflector_name, substrate_name])
            interpolated_stack = self.material_manager.get_interpolated_stack(
                list(set(materials_to_load)),
                self.lambda_grid_um,
                interp_method="pchip",
            )

            layer_stack_def = [{"n": interpolated_stack[layer["name"]], "d": layer["d_nm"] * 1e-9} for layer in base_structure_layers]
            layer_stack_def.append({"n": interpolated_stack[base_reflector["name"]], "d": base_reflector["d_nm"] * 1e-9})
            layer_stack_def.append({"n": interpolated_stack[base_substrate["name"]], "d": np.inf})

            R_s, R_p = calculate_TMM_core(layer_stack_def, self.spectral_manager.lambda_m, theta0_deg=0.0)
            R_avg = (R_s + R_p) / 2.0
            self.last_absorptance = 1.0 - R_avg

            self.loaded_structure_text = self.tr("已加载: ", "Loaded: ") + base_structure_str
            self.lbl_loaded_structure.setText(self.loaded_structure_text)
            self.plot_spectral_analysis()
        except Exception as e:
            self.last_absorptance = None
            self.loaded_structure_text = ""
            QMessageBox.critical(self, self.tr("加载失败", "Load Failed"), str(e))

    def plot_spectral_analysis(self):
        if self.last_absorptance is None:
            return

        spec = self.spectral_manager

        self.plot_widget_solar.clear()
        self.plot_widget_solar.plot(self.lambda_grid_um, self.last_absorptance, pen=pg.mkPen("k", width=1.5), name=self.tr("吸收率", "Absorptance"))
        fill_solar = pg.FillBetweenItem(
            pg.PlotDataItem(self.lambda_grid_um, spec.IAM1_5_norm_masked, pen=pg.mkPen(None)),
            pg.PlotDataItem(self.lambda_grid_um, np.zeros_like(self.lambda_grid_um), pen=pg.mkPen(None)),
            brush=pg.mkBrush(230, 50, 50, 70),
        )
        self.plot_widget_solar.addItem(fill_solar)

        self.plot_widget_atm.clear()
        self.plot_widget_atm.plot(self.lambda_grid_um, self.last_absorptance, pen=pg.mkPen("k", width=1.5), name=self.tr("吸收率", "Absorptance"))
        atm_trans_masked = np.zeros_like(self.lambda_grid_um)
        atm_trans_masked[spec.idx_thermal] = spec.atm_transmittance[spec.idx_thermal]
        fill_atm = pg.FillBetweenItem(
            pg.PlotDataItem(self.lambda_grid_um, atm_trans_masked, pen=pg.mkPen(None)),
            pg.PlotDataItem(self.lambda_grid_um, np.zeros_like(self.lambda_grid_um), pen=pg.mkPen(None)),
            brush=pg.mkBrush(50, 50, 230, 70),
        )
        self.plot_widget_atm.addItem(fill_atm)

    def _precompute_powers(self) -> bool:
        if self.last_absorptance is None:
            QMessageBox.warning(self, self.tr("错误", "Error"), self.tr("请先从 TMM 页面加载光谱。", "Please load a spectrum from the TMM tab first."))
            return False

        try:
            T_amb = float(self.edit_tamb.text())
        except ValueError:
            QMessageBox.warning(self, self.tr("输入错误", "Input Error"), self.tr("无效的环境温度 T_amb。", "Invalid ambient temperature T_amb."))
            return False

        if self.last_P_atm is None or self.last_P_sum is None or self.last_T_amb != T_amb:
            self.plot_widget_pcool.setTitle(self.tr("正在计算 P_sum 和 P_atm...", "Computing P_sum and P_atm..."))
            QApplication.processEvents()
            self.last_P_sum = cooling_calc.calculate_P_sum(self.last_absorptance, self.spectral_manager)
            self.last_P_atm = cooling_calc.calculate_P_atm(T_amb, self.last_absorptance, self.spectral_manager)
            self.last_T_amb = T_amb
            self.lbl_log_psum.setText(
                self.tr(f"P_sum (太阳吸收) = {self.last_P_sum:.4f} W/m^2", f"P_sum (Solar Absorption) = {self.last_P_sum:.4f} W/m^2")
            )
            self.lbl_log_patm.setText(
                self.tr(f"P_atm (大气吸收) = {self.last_P_atm:.4f} W/m^2", f"P_atm (Atmospheric Absorption) = {self.last_P_atm:.4f} W/m^2")
            )
        return True

    def run_cooling_calculation(self):
        if not self._precompute_powers():
            return

        try:
            T_amb = self.last_T_amb
            hc_values = [float(hc.strip()) for hc in self.edit_hc_values.text().split(",") if hc.strip()]
            T_min = float(self.edit_tsample_min.text())
            T_max = float(self.edit_tsample_max.text())
            T_pts = int(self.edit_tsample_points.text())
            T_sample_range = np.linspace(T_min, T_max, T_pts)
            if T_pts < 2:
                raise ValueError(self.tr("扫描点数必须 >= 2。", "Point count must be >= 2."))
            if not hc_values:
                raise ValueError(self.tr("至少需要一个 hc 值。", "At least one hc value is required."))
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("输入错误", "Input Error"),
                self.tr(f"无效的扫描参数: {e}", f"Invalid sweep parameters: {e}"),
            )
            return

        self.plot_widget_pcool.setTitle(self.tr("正在扫描 T_sample ...", "Scanning T_sample ..."))
        QApplication.processEvents()

        try:
            T_range, Pcool_matrix = cooling_calc.run_cooling_sweep(
                self.last_absorptance,
                self.spectral_manager,
                T_amb,
                hc_values,
                T_sample_range,
                P_atm=self.last_P_atm,
                P_sum=self.last_P_sum,
            )

            self.plot_widget_pcool.clear()
            self.plot_widget_pcool.addLegend()
            colors = [(0, 114, 189), (217, 83, 25), (237, 177, 32), (126, 47, 142), (119, 172, 48), (77, 190, 238)]
            for i, hc in enumerate(hc_values):
                color = colors[i % len(colors)]
                self.plot_widget_pcool.plot(T_range, Pcool_matrix[:, i], pen=pg.mkPen(color, width=2.5), name=f"hc = {hc} W/m^2K")

            self.plot_widget_pcool.setTitle(
                self.tr(f"净冷却功率 (T_amb = {T_amb} K)", f"Net Cooling Power (T_amb = {T_amb} K)")
            )
            self.plot_widget_pcool.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen("k", style=Qt.DashLine)))
            self.plot_widget_pcool.setYRange(np.min(Pcool_matrix) - 10, np.max(Pcool_matrix) + 10)
            self.plot_widget_pcool.setXRange(T_min, T_max)

            self.edit_hc_eq.setText(str(hc_values[0]))
            self.on_calc_equilibrium(auto_call=True)
        except Exception as e:
            QMessageBox.critical(self, self.tr("计算失败", "Calculation Failed"), str(e))
            self.plot_widget_pcool.setTitle(self.tr("计算失败", "Calculation Failed"))

    def on_calc_equilibrium(self, auto_call=False):
        if not self._precompute_powers():
            self._reset_result_labels(self.edit_hc_eq.text() or "--")
            return

        try:
            hc_eq = float(self.edit_hc_eq.text())
        except ValueError:
            self._reset_result_labels(self.edit_hc_eq.text() or "--")
            if not auto_call:
                QMessageBox.warning(self, self.tr("输入错误", "Input Error"), self.tr("HC 系数格式无效。", "The HC value is invalid."))
            return

        try:
            T_eq, T_drop = cooling_calc.find_equilibrium_temp(
                hc_eq,
                self.last_T_amb,
                self.last_P_atm,
                self.last_P_sum,
                self.last_absorptance,
                self.spectral_manager,
            )

            if np.isnan(T_eq) or np.isnan(T_drop):
                self._show_equilibrium_unavailable(hc_eq)
                if not auto_call:
                    QMessageBox.information(self, self.tr("未找到平衡点", "No Equilibrium Found"), self.tr("当前参数范围内未找到 T_eq。", "No T_eq was found within the current parameter range."))
                return

            Prad_at_Teq = cooling_calc.calculate_P_rad(T_eq, self.last_absorptance, self.spectral_manager)
            Pnon_at_Teq = cooling_calc.calculate_P_non(T_eq, self.last_T_amb, hc_eq)
            self.lbl_eq_temp_result.setText(f"T_eq = {T_eq:.2f} K")
            self.lbl_eq_drop_result.setText(self.tr(f"降温量 Delta T = {T_drop:.2f} K", f"Delta T (Cooling) = {T_drop:.2f} K"))
            self.lbl_log_prad.setText(f"P_rad (T_eq) = {Prad_at_Teq:.4f} W/m^2")
            self.lbl_log_pnon.setText(f"P_non (T_eq, hc={hc_eq:g}) = {Pnon_at_Teq:.4f} W/m^2")
        except Exception as e:
            self._reset_result_labels(f"{hc_eq:g}")
            if not auto_call:
                QMessageBox.critical(self, self.tr("T_eq 计算失败", "T_eq Calculation Failed"), str(e))
