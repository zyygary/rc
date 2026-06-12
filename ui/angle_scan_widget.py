from typing import Any, Dict, List

import numpy as np
import pyqtgraph as pg
from PySide2.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.constants import LAMBDA_GRID_UM
from core.material_manager import MaterialManager
from core.spectral_manager import SpectralDataManager
from core.tmm_core import calculate_TMM_core
from core.utils import calculate_weighted_averages
from ui.i18n import LANGUAGE_EN, normalize_language, tr
from ui.tmm_simulator_widget import TmmSimulatorWidget


class AngleScanWidget(QWidget):
    base_structure_layers: List[Dict[str, Any]] = []
    base_structure_str: str = ""
    base_reflector: Dict[str, Any] = {}
    base_substrate: Dict[str, Any] = {}

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
        self.lambda_grid_um = LAMBDA_GRID_UM
        self.setup_ui()
        self.set_language(self.language)

    def tr(self, zh_text: str, en_text: str) -> str:
        return tr(self.language, zh_text, en_text)

    def _polarization_items(self):
        if self.language == LANGUAGE_EN:
            return ["Average (Avg)", "S-Pol (TE)", "P-Pol (TM)"]
        return ["平均 (Avg)", "S-偏振 (TE)", "P-偏振 (TM)"]

    def _current_pol_code(self):
        index = self.combo_pol.currentIndex()
        if index == 1:
            return "S"
        if index == 2:
            return "P"
        return "Avg"

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        load_layout = QHBoxLayout()
        self.btn_load_structure = QPushButton()
        self.lbl_loaded_structure = QLabel()
        self.lbl_loaded_structure.setWordWrap(True)
        self.lbl_loaded_structure.setStyleSheet("font-size: 9pt;")
        load_layout.addWidget(self.btn_load_structure)
        load_layout.addWidget(self.lbl_loaded_structure, 1)
        main_layout.addLayout(load_layout)

        self.settings_group = QGroupBox()
        settings_layout = QHBoxLayout()

        self.lbl_pol = QLabel()
        settings_layout.addWidget(self.lbl_pol)
        self.combo_pol = QComboBox()
        settings_layout.addWidget(self.combo_pol)

        self.btn_run_angle_scan = QPushButton()
        self.btn_run_angle_scan.setObjectName("CalculateButton")
        settings_layout.addWidget(self.btn_run_angle_scan)
        settings_layout.addStretch()

        self.settings_group.setLayout(settings_layout)
        main_layout.addWidget(self.settings_group)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setYRange(0, 1)
        self.plot_widget.setXRange(0, 90)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend()
        main_layout.addWidget(self.plot_widget, 1)

        self.btn_load_structure.clicked.connect(self.load_structure_from_tmm_tab)
        self.btn_run_angle_scan.clicked.connect(self.run_angle_scan)
        self.combo_pol.currentTextChanged.connect(self.run_angle_scan)

    def set_language(self, language):
        self.language = normalize_language(language)
        self.btn_load_structure.setText(self.tr("加载当前 TMM 结构", "Load Current TMM Structure"))
        self.lbl_loaded_structure.setText(self.tr("未加载结构。", "No structure loaded."))
        self.settings_group.setTitle(self.tr("角度扫描设置", "Angle Scan Settings"))
        self.lbl_pol.setText(self.tr("偏振:", "Polarization:"))
        current_index = self.combo_pol.currentIndex()
        self.combo_pol.blockSignals(True)
        self.combo_pol.clear()
        self.combo_pol.addItems(self._polarization_items())
        self.combo_pol.setCurrentIndex(max(current_index, 0))
        self.combo_pol.blockSignals(False)
        self.btn_run_angle_scan.setText(self.tr("运行角度扫描", "Run Angle Scan"))
        self.plot_widget.setTitle(self.tr("加权光学响应 vs 入射角", "Weighted Optical Response vs Incident Angle"))
        self.plot_widget.setLabel("bottom", self.tr("入射角 (deg)", "Incident Angle (deg)"))
        self.plot_widget.setLabel("left", self.tr("加权响应 (Eps_bar, Rho_bar)", "Weighted Response (Eps_bar, Rho_bar)"))

    def load_structure_from_tmm_tab(self):
        layers_widgets = self.tmm_sim.layer_widgets
        reflector_name = self.tmm_sim.combo_reflector.currentText()
        substrate_name = self.tmm_sim.combo_substrate.currentText()
        try:
            reflector_thick_nm = float(self.tmm_sim.edit_reflector_thick.text())
        except ValueError:
            QMessageBox.warning(
                self,
                self.tr("加载失败", "Load Failed"),
                self.tr("TMM 页面中的反射层厚度无效。", "The reflector thickness in the TMM tab is invalid."),
            )
            return
        if not layers_widgets:
            QMessageBox.warning(
                self,
                self.tr("加载失败", "Load Failed"),
                self.tr("TMM 页面中没有功能层。", "There are no functional layers in the TMM tab."),
            )
            return

        self.base_structure_layers = []
        self.base_structure_str = ""

        for layer_index, layer in enumerate(layers_widgets, start=1):
            mat_name = layer.combo_material.currentText()
            try:
                thick_nm = float(layer.edit_thickness.text())
            except ValueError:
                QMessageBox.warning(
                    self,
                    self.tr("加载失败", "Load Failed"),
                    self.tr(
                        f"TMM 页面中层 {mat_name} 的厚度无效。",
                        f"The thickness of layer {mat_name} in the TMM tab is invalid.",
                    ),
                )
                return
            self.base_structure_layers.append({"name": mat_name, "d_nm": thick_nm})
            self.base_structure_str += f"L{layer_index}: {mat_name} ({thick_nm}nm) / "

        self.base_reflector = {"name": reflector_name, "d_nm": reflector_thick_nm}
        self.base_substrate = {"name": substrate_name, "d_nm": np.inf}
        self.base_structure_str += f"{reflector_name}({reflector_thick_nm}nm) / {substrate_name}"

        self.lbl_loaded_structure.setText(
            self.tr("已加载: ", "Loaded: ") + self.base_structure_str
        )
        self.run_angle_scan()

    def run_angle_scan(self, _=None):
        if not self.base_structure_layers:
            return

        try:
            materials_to_load = [layer["name"] for layer in self.base_structure_layers]
            materials_to_load.append(self.base_reflector["name"])
            materials_to_load.append(self.base_substrate["name"])

            interpolated_stack = self.material_manager.get_interpolated_stack(
                list(set(materials_to_load)),
                self.lambda_grid_um,
                interp_method="pchip",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("计算错误", "Calculation Error"),
                self.tr(f"插值材料失败: {e}", f"Failed to interpolate materials: {e}"),
            )
            return

        layer_stack_def = []
        for layer in self.base_structure_layers:
            layer_stack_def.append({"n": interpolated_stack[layer["name"]], "d": layer["d_nm"] * 1e-9})
        layer_stack_def.append({"n": interpolated_stack[self.base_reflector["name"]], "d": self.base_reflector["d_nm"] * 1e-9})
        layer_stack_def.append({"n": interpolated_stack[self.base_substrate["name"]], "d": np.inf})

        angles = np.arange(0, 90, 1)
        results_eps_s, results_rho_s = [], []
        results_eps_p, results_rho_p = [], []
        results_eps_avg, results_rho_avg = [], []

        self.plot_widget.setTitle(self.tr("正在扫描 0-89 度 (90 点)...", "Scanning 0-89 degrees (90 points)..."))
        QApplication.processEvents()

        try:
            for angle in angles:
                R_s, R_p = calculate_TMM_core(
                    layer_stack_def,
                    self.spectral_manager.lambda_m,
                    theta0_deg=float(angle),
                )

                E_s = 1.0 - R_s
                E_p = 1.0 - R_p
                R_avg = (R_s + R_p) / 2.0
                E_avg = (E_s + E_p) / 2.0

                eps_bar_s, rho_bar_s = calculate_weighted_averages(E_s, R_s, self.spectral_manager)
                eps_bar_p, rho_bar_p = calculate_weighted_averages(E_p, R_p, self.spectral_manager)
                eps_bar_avg, rho_bar_avg = calculate_weighted_averages(E_avg, R_avg, self.spectral_manager)

                results_eps_s.append(eps_bar_s)
                results_rho_s.append(rho_bar_s)
                results_eps_p.append(eps_bar_p)
                results_rho_p.append(rho_bar_p)
                results_eps_avg.append(eps_bar_avg)
                results_rho_avg.append(rho_bar_avg)
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("计算错误", "Calculation Error"),
                self.tr(f"角度扫描失败: {e}", f"Angle scan failed: {e}"),
            )
            self.plot_widget.setTitle(self.tr(f"扫描失败: {e}", f"Scan failed: {e}"))
            return

        self.plot_widget.clear()

        pol_code = self._current_pol_code()
        if pol_code == "S":
            self.plot_widget.plot(angles, results_rho_s, pen=pg.mkPen("#007BFF", width=2.5), name="Rho_bar (S)")
            self.plot_widget.plot(angles, results_eps_s, pen=pg.mkPen("#DC3545", width=2.5), name="Eps_bar (S)")
        elif pol_code == "P":
            self.plot_widget.plot(angles, results_rho_p, pen=pg.mkPen("#007BFF", width=2.5), name="Rho_bar (P)")
            self.plot_widget.plot(angles, results_eps_p, pen=pg.mkPen("#DC3545", width=2.5), name="Eps_bar (P)")
        else:
            self.plot_widget.plot(angles, results_rho_avg, pen=pg.mkPen("#007BFF", width=2.5), name="Rho_bar (Avg)")
            self.plot_widget.plot(angles, results_eps_avg, pen=pg.mkPen("#DC3545", width=2.5), name="Eps_bar (Avg)")

        display_pol = self.combo_pol.currentText()
        self.plot_widget.setTitle(
            self.tr(f"加权光学响应 ({display_pol})", f"Weighted Optical Response ({display_pol})")
        )
