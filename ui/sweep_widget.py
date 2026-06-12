from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.constants import LAMBDA_GRID_UM, LAMBDA_MIN_UM
from core.material_manager import MaterialManager
from core.spectral_manager import SpectralDataManager
from core.tmm_core import calculate_TMM_core
from core.utils import calculate_weighted_averages
from ui.i18n import normalize_language, tr

if TYPE_CHECKING:
    from ui.tmm_simulator_widget import TmmSimulatorWidget

MAX_THICKNESS_NM = 100_000.0


class _LayerSliderControl(QFrame):
    sliderReleased = Signal()

    def __init__(self, layer_name: str, current_nm: float, max_nm: float = 10000, parent=None, language="zh"):
        super().__init__(parent)
        self.language = normalize_language(language)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
        self.lbl_name = QLabel(layer_name)
        self.txt_current = QLineEdit(f"{current_nm:.0f}")
        self.txt_current.setFixedWidth(80)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.txt_max = QLineEdit(f"{max_nm:.0f}")
        self.txt_max.setFixedWidth(80)
        self.txt_max.setPlaceholderText("Max (nm)")
        self.lbl_current = QLabel()
        main_layout = QVBoxLayout(self)
        line1_layout = QHBoxLayout()
        line2_layout = QHBoxLayout()
        line1_layout.addWidget(self.lbl_name)
        line1_layout.addStretch()
        line1_layout.addWidget(self.lbl_current)
        line1_layout.addWidget(self.txt_current)
        line2_layout.addWidget(self.slider)
        line2_layout.addWidget(self.txt_max)
        main_layout.addLayout(line1_layout)
        main_layout.addLayout(line2_layout)
        self.connect_signals()
        self.set_language(self.language)
        self.update_slider_from_text()

    def tr(self, zh_text: str, en_text: str) -> str:
        return tr(self.language, zh_text, en_text)

    def set_language(self, language):
        self.language = normalize_language(language)
        self.lbl_current.setText(self.tr("当前 (nm):", "Current (nm):"))
        self.txt_current.setToolTip(self.tr("输入数值后按 Enter 更新。", "Enter a value and press Enter to update."))

    def connect_signals(self):
        self.slider.valueChanged.connect(self.update_text_from_slider)
        self.txt_max.returnPressed.connect(self.update_slider_from_text)
        self.slider.valueChanged.connect(self.trigger_recalc)
        self.txt_current.returnPressed.connect(self.trigger_recalc)

    def _get_fval(self, qedit: QLineEdit, default: float = 0.0) -> float:
        try:
            return float(qedit.text())
        except ValueError:
            return default

    def update_text_from_slider(self, value: int):
        min_nm = 0.0
        max_nm = self._get_fval(self.txt_max, 10000)
        val_0_1 = value / 1000.0
        current_nm = min_nm + (max_nm - min_nm) * val_0_1
        self.txt_current.blockSignals(True)
        self.txt_current.setText(f"{current_nm:.0f}")
        self.txt_current.blockSignals(False)

    def update_slider_from_text(self):
        current_nm = self._get_fval(self.txt_current)
        min_nm = 0.0
        max_nm = self._get_fval(self.txt_max, 10000)
        if max_nm <= min_nm:
            max_nm = 10000.0
        self.txt_max.setText(f"{max_nm:.0f}")
        current_nm = max(min_nm, min(max_nm, current_nm))

        self.txt_current.blockSignals(True)
        self.txt_current.setText(f"{current_nm:.0f}")
        self.txt_current.blockSignals(False)

        val_0_1 = 0.0
        if max_nm > 0.001:
            val_0_1 = (current_nm - min_nm) / (max_nm - min_nm)

        self.slider.blockSignals(True)
        self.slider.setValue(int(val_0_1 * 1000))
        self.slider.blockSignals(False)

    def trigger_recalc(self):
        self.update_slider_from_text()
        self.sliderReleased.emit()

    def get_value_nm(self) -> float:
        self.update_slider_from_text()
        return self._get_fval(self.txt_current)


class SweepWidget(QWidget):
    def __init__(
        self,
        material_manager: MaterialManager,
        spectral_manager: SpectralDataManager,
        tmm_simulator: "TmmSimulatorWidget",
        parent=None,
        language="zh",
    ):
        super().__init__(parent)
        self.language = normalize_language(language)
        self.material_manager = material_manager
        self.spectral_manager = spectral_manager
        self.tmm_sim = tmm_simulator
        self.lambda_grid_um = LAMBDA_GRID_UM

        self.base_structure_layers: List[Dict[str, Any]] = []
        self.base_structure_str: str = ""
        self.base_reflector: Dict[str, Any] = {}
        self.base_substrate: Dict[str, Any] = {}

        self.fn1_slider_widgets: List[_LayerSliderControl] = []
        self.setup_ui()
        self.set_language(self.language)

    def tr(self, zh_text: str, en_text: str) -> str:
        return tr(self.language, zh_text, en_text)

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
        settings_layout = QVBoxLayout()
        mode_layout = QHBoxLayout()
        self.radio_mode_spectrum = QRadioButton()
        self.radio_mode_1d_sweep = QRadioButton()
        self.radio_mode_2d_sweep = QRadioButton()
        self.radio_mode_spectrum.setChecked(True)
        mode_layout.addWidget(self.radio_mode_spectrum)
        mode_layout.addWidget(self.radio_mode_1d_sweep)
        mode_layout.addWidget(self.radio_mode_2d_sweep)
        settings_layout.addLayout(mode_layout)
        self.settings_group.setLayout(settings_layout)
        main_layout.addWidget(self.settings_group)

        self.stacked_widget = QStackedWidget()
        self.setup_fn1_interactive_ui()
        self.setup_fn2_1d_sweep_ui()
        self.setup_fn3_2d_sweep_ui()
        self.stacked_widget.addWidget(self.fn1_widget)
        self.stacked_widget.addWidget(self.fn2_widget)
        self.stacked_widget.addWidget(self.fn3_widget)
        main_layout.addWidget(self.stacked_widget, 1)

        self.btn_load_structure.clicked.connect(self.load_structure_from_tmm_tab)
        self.radio_mode_spectrum.toggled.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.radio_mode_1d_sweep.toggled.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.radio_mode_2d_sweep.toggled.connect(lambda: self.stacked_widget.setCurrentIndex(2))

    def setup_fn1_interactive_ui(self):
        self.fn1_widget = QWidget()
        layout = QHBoxLayout(self.fn1_widget)
        control_panel = QFrame()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setFixedWidth(400)
        self.fn1_lbl_control = QLabel()
        control_layout.addWidget(self.fn1_lbl_control)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.fn1_slider_layout = QVBoxLayout(scroll_widget)
        self.fn1_slider_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(scroll_widget)
        control_layout.addWidget(scroll_area)
        layout.addWidget(control_panel)
        self.fn1_plot_widget = pg.PlotWidget()
        self.fn1_plot_widget.setYRange(0, 1)
        self.fn1_plot_widget.setXRange(LAMBDA_MIN_UM, 13.0)
        self.fn1_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.fn1_plot_widget.addLegend()
        layout.addWidget(self.fn1_plot_widget)

    def setup_fn2_1d_sweep_ui(self):
        self.fn2_widget = QWidget()
        layout = QHBoxLayout(self.fn2_widget)
        control_panel = QFrame()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setFixedWidth(300)
        self.fn2_lbl_select = QLabel()
        control_layout.addWidget(self.fn2_lbl_select)
        self.combo_scan_layer = QComboBox()
        self.combo_scan_layer.setEnabled(False)
        control_layout.addWidget(self.combo_scan_layer)
        control_layout.addSpacing(10)

        min_layout = QHBoxLayout()
        self.fn2_lbl_min = QLabel("Min (nm):")
        min_layout.addWidget(self.fn2_lbl_min)
        self.fn2_slider_min = QSlider(Qt.Horizontal)
        self.fn2_slider_min.setRange(0, 20000)
        self.fn2_txt_min = QLineEdit("0")
        self.fn2_txt_min.setFixedWidth(80)
        min_layout.addWidget(self.fn2_slider_min)
        min_layout.addWidget(self.fn2_txt_min)

        max_layout = QHBoxLayout()
        self.fn2_lbl_max = QLabel("Max (nm):")
        max_layout.addWidget(self.fn2_lbl_max)
        self.fn2_slider_max = QSlider(Qt.Horizontal)
        self.fn2_slider_max.setRange(0, 20000)
        self.fn2_slider_max.setValue(20000)
        self.fn2_txt_max = QLineEdit("20000")
        self.fn2_txt_max.setFixedWidth(80)
        max_layout.addWidget(self.fn2_slider_max)
        max_layout.addWidget(self.fn2_txt_max)

        control_layout.addLayout(min_layout)
        control_layout.addLayout(max_layout)
        control_layout.addSpacing(10)
        self.fn2_lbl_points = QLabel()
        control_layout.addWidget(self.fn2_lbl_points)
        self.fn2_edit_points = QLineEdit("50")
        control_layout.addWidget(self.fn2_edit_points)
        control_layout.addStretch()
        layout.addWidget(control_panel)

        self.fn2_plot_widget = pg.PlotWidget()
        self.fn2_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.fn2_plot_widget.addLegend()
        layout.addWidget(self.fn2_plot_widget)

        self.fn2_slider_min.valueChanged.connect(self._fn2_update_min_text)
        self.fn2_txt_min.returnPressed.connect(self._fn2_update_min_slider)
        self.fn2_slider_max.valueChanged.connect(self._fn2_update_max_text)
        self.fn2_txt_max.returnPressed.connect(self._fn2_update_max_slider)
        self.combo_scan_layer.currentTextChanged.connect(self.run_1d_sweep)
        self.fn2_slider_min.sliderReleased.connect(self.run_1d_sweep)
        self.fn2_txt_min.returnPressed.connect(self.run_1d_sweep)
        self.fn2_slider_max.sliderReleased.connect(self.run_1d_sweep)
        self.fn2_txt_max.returnPressed.connect(self.run_1d_sweep)
        self.fn2_edit_points.returnPressed.connect(self.run_1d_sweep)

    def setup_fn3_2d_sweep_ui(self):
        self.fn3_widget = QWidget()
        layout = QGridLayout(self.fn3_widget)
        control_panel = QFrame()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setFixedWidth(350)

        self.fn3_lbl_layer_x = QLabel()
        control_layout.addWidget(self.fn3_lbl_layer_x)
        self.fn3_combo_layer_x = QComboBox()
        self.fn3_combo_layer_x.setEnabled(False)
        control_layout.addWidget(self.fn3_combo_layer_x)

        self.fn3_lbl_layer_y = QLabel()
        control_layout.addWidget(self.fn3_lbl_layer_y)
        self.fn3_combo_layer_y = QComboBox()
        self.fn3_combo_layer_y.setEnabled(False)
        control_layout.addWidget(self.fn3_combo_layer_y)
        control_layout.addSpacing(10)

        x_layout = QHBoxLayout()
        self.fn3_lbl_x_range = QLabel()
        x_layout.addWidget(self.fn3_lbl_x_range)
        self.fn3_slider_x_min = QSlider(Qt.Horizontal)
        self.fn3_slider_x_min.setRange(0, 20000)
        self.fn3_txt_x_min = QLineEdit("0")
        self.fn3_txt_x_min.setFixedWidth(60)
        self.fn3_slider_x_max = QSlider(Qt.Horizontal)
        self.fn3_slider_x_max.setRange(0, 20000)
        self.fn3_slider_x_max.setValue(5000)
        self.fn3_txt_x_max = QLineEdit("5000")
        self.fn3_txt_x_max.setFixedWidth(60)
        x_layout.addWidget(self.fn3_slider_x_min)
        x_layout.addWidget(self.fn3_txt_x_min)
        x_layout.addWidget(self.fn3_slider_x_max)
        x_layout.addWidget(self.fn3_txt_x_max)
        control_layout.addLayout(x_layout)

        y_layout = QHBoxLayout()
        self.fn3_lbl_y_range = QLabel()
        y_layout.addWidget(self.fn3_lbl_y_range)
        self.fn3_slider_y_min = QSlider(Qt.Horizontal)
        self.fn3_slider_y_min.setRange(0, 20000)
        self.fn3_txt_y_min = QLineEdit("0")
        self.fn3_txt_y_min.setFixedWidth(60)
        self.fn3_slider_y_max = QSlider(Qt.Horizontal)
        self.fn3_slider_y_max.setRange(0, 20000)
        self.fn3_slider_y_max.setValue(5000)
        self.fn3_txt_y_max = QLineEdit("5000")
        self.fn3_txt_y_max.setFixedWidth(60)
        y_layout.addWidget(self.fn3_slider_y_min)
        y_layout.addWidget(self.fn3_txt_y_min)
        y_layout.addWidget(self.fn3_slider_y_max)
        y_layout.addWidget(self.fn3_txt_y_max)
        control_layout.addLayout(y_layout)
        control_layout.addSpacing(10)

        points_layout = QHBoxLayout()
        self.fn3_lbl_points_x = QLabel()
        points_layout.addWidget(self.fn3_lbl_points_x)
        self.fn3_edit_points_x = QLineEdit("30")
        points_layout.addWidget(self.fn3_edit_points_x)
        self.fn3_lbl_points_y = QLabel()
        points_layout.addWidget(self.fn3_lbl_points_y)
        self.fn3_edit_points_y = QLineEdit("30")
        points_layout.addWidget(self.fn3_edit_points_y)
        control_layout.addLayout(points_layout)

        self.fn3_lbl_output = QLabel()
        control_layout.addWidget(self.fn3_lbl_output)
        self.fn3_combo_output = QComboBox()
        control_layout.addWidget(self.fn3_combo_output)
        control_layout.addSpacing(10)

        self.fn3_btn_run_sweep = QPushButton()
        self.fn3_btn_run_sweep.setObjectName("CalculateButton")
        control_layout.addWidget(self.fn3_btn_run_sweep)
        control_layout.addStretch()
        layout.addWidget(control_panel, 0, 0)

        self.fn3_plot_widget = pg.PlotWidget()
        self.fn3_image_item = pg.ImageItem()
        self.fn3_plot_widget.addItem(self.fn3_image_item)
        self.fn3_hist_lut = pg.HistogramLUTWidget()
        self.fn3_hist_lut.setImageItem(self.fn3_image_item)
        self.fn3_hist_lut.setMaximumWidth(150)
        cmap = pg.ColorMap([0.0, 0.5, 1.0], [(0, 0, 255, 255), (255, 255, 0, 255), (255, 0, 0, 255)])
        self.fn3_hist_lut.gradient.setColorMap(cmap)
        layout.addWidget(self.fn3_plot_widget, 0, 1)
        layout.addWidget(self.fn3_hist_lut, 0, 2)

        self.fn3_slider_x_min.valueChanged.connect(self._fn3_update_xmin_text)
        self.fn3_txt_x_min.returnPressed.connect(self._fn3_update_xmin_slider)
        self.fn3_slider_x_max.valueChanged.connect(self._fn3_update_xmax_text)
        self.fn3_txt_x_max.returnPressed.connect(self._fn3_update_xmax_slider)
        self.fn3_slider_y_min.valueChanged.connect(self._fn3_update_ymin_text)
        self.fn3_txt_y_min.returnPressed.connect(self._fn3_update_ymin_slider)
        self.fn3_slider_y_max.valueChanged.connect(self._fn3_update_ymax_text)
        self.fn3_txt_y_max.returnPressed.connect(self._fn3_update_ymax_slider)
        self.fn3_btn_run_sweep.clicked.connect(self.run_2d_sweep)

    def set_language(self, language):
        self.language = normalize_language(language)
        self.btn_load_structure.setText(self.tr("加载当前 TMM 结构", "Load Current TMM Structure"))
        if self.base_structure_str:
            self.lbl_loaded_structure.setText(self.tr("已加载: ", "Loaded: ") + self.base_structure_str)
        else:
            self.lbl_loaded_structure.setText(self.tr("未加载结构。", "No structure loaded."))
        self.settings_group.setTitle(self.tr("扫描模式", "Sweep Modes"))
        self.radio_mode_spectrum.setText(self.tr("模式 1: 交互式厚度控制", "Mode 1: Interactive Thickness Control"))
        self.radio_mode_1d_sweep.setText(self.tr("模式 2: 1D 性能曲线", "Mode 2: 1D Performance Curve"))
        self.radio_mode_2d_sweep.setText(self.tr("模式 3: 2D 热力图", "Mode 3: 2D Heatmap"))
        self.fn1_lbl_control.setText(self.tr("层厚度 (nm):", "Layer Thickness (nm):"))
        self.fn1_plot_widget.setTitle(self.tr("发射率光谱 (厚度控制)", "Emissivity Spectrum (Thickness Control)"))
        self.fn1_plot_widget.setLabel("bottom", self.tr("波长 (um)", "Wavelength (um)"))
        self.fn1_plot_widget.setLabel("left", self.tr("光学响应", "Optical Response"))
        self.fn2_lbl_select.setText(self.tr("选择要扫描的层", "Select Layer to Sweep"))
        self.fn2_lbl_points.setText(self.tr("扫描点数:", "Number of Points:"))
        self.fn2_plot_widget.setTitle(self.tr("加权性能", "Weighted Performance"))
        self.fn2_plot_widget.setLabel("bottom", self.tr("厚度 (nm)", "Thickness (nm)"))
        self.fn2_plot_widget.setLabel("left", self.tr("加权性能", "Weighted Metric"))
        self.fn3_lbl_layer_x.setText(self.tr("选择扫描层 X:", "Select Sweep Layer X:"))
        self.fn3_lbl_layer_y.setText(self.tr("选择扫描层 Y:", "Select Sweep Layer Y:"))
        self.fn3_lbl_x_range.setText(self.tr("X 轴 Min/Max (nm):", "X Axis Min/Max (nm):"))
        self.fn3_lbl_y_range.setText(self.tr("Y 轴 Min/Max (nm):", "Y Axis Min/Max (nm):"))
        self.fn3_lbl_points_x.setText(self.tr("点数 (X):", "Points (X):"))
        self.fn3_lbl_points_y.setText(self.tr("点数 (Y):", "Points (Y):"))
        self.fn3_lbl_output.setText(self.tr("选择输出:", "Select Output:"))
        current_output_index = self.fn3_combo_output.currentIndex()
        self.fn3_combo_output.blockSignals(True)
        self.fn3_combo_output.clear()
        self.fn3_combo_output.addItems(
            [
                self.tr("加权发射率 (Eps_bar)", "Weighted Emissivity (Eps_bar)"),
                self.tr("加权反射率 (Rho_bar)", "Weighted Reflectance (Rho_bar)"),
            ]
        )
        self.fn3_combo_output.setCurrentIndex(max(current_output_index, 0))
        self.fn3_combo_output.blockSignals(False)
        self.fn3_btn_run_sweep.setText(self.tr("运行 2D 扫描", "Run 2D Sweep"))
        if not self.base_structure_str:
            self.fn3_plot_widget.setTitle(self.tr("2D 扫描热力图 (未加载)", "2D Scan Heatmap (Not Loaded)"))

        for widget in self.fn1_slider_widgets:
            widget.set_language(self.language)

    def _fn2_update_min_text(self, value):
        self.fn2_txt_min.setText(str(value))
        if value > self.fn2_slider_max.value():
            self.fn2_slider_max.setValue(value)

    def _fn2_update_min_slider(self):
        try:
            self.fn2_slider_min.setValue(int(self.fn2_txt_min.text()))
        except ValueError:
            pass

    def _fn2_update_max_text(self, value):
        self.fn2_txt_max.setText(str(value))
        if value < self.fn2_slider_min.value():
            self.fn2_slider_min.setValue(value)

    def _fn2_update_max_slider(self):
        try:
            self.fn2_slider_max.setValue(int(self.fn2_txt_max.text()))
        except ValueError:
            pass

    def _fn3_update_xmin_text(self, value):
        self.fn3_txt_x_min.setText(str(value))
        if value > self.fn3_slider_x_max.value():
            self.fn3_slider_x_max.setValue(value)

    def _fn3_update_xmin_slider(self):
        try:
            self.fn3_slider_x_min.setValue(int(self.fn3_txt_x_min.text()))
        except ValueError:
            pass

    def _fn3_update_xmax_text(self, value):
        self.fn3_txt_x_max.setText(str(value))
        if value < self.fn3_slider_x_min.value():
            self.fn3_slider_x_min.setValue(value)

    def _fn3_update_xmax_slider(self):
        try:
            self.fn3_slider_x_max.setValue(int(self.fn3_txt_x_max.text()))
        except ValueError:
            pass

    def _fn3_update_ymin_text(self, value):
        self.fn3_txt_y_min.setText(str(value))
        if value > self.fn3_slider_y_max.value():
            self.fn3_slider_y_max.setValue(value)

    def _fn3_update_ymin_slider(self):
        try:
            self.fn3_slider_y_min.setValue(int(self.fn3_txt_y_min.text()))
        except ValueError:
            pass

    def _fn3_update_ymax_text(self, value):
        self.fn3_txt_y_max.setText(str(value))
        if value < self.fn3_slider_y_min.value():
            self.fn3_slider_y_min.setValue(value)

    def _fn3_update_ymax_slider(self):
        try:
            self.fn3_slider_y_max.setValue(int(self.fn3_txt_y_max.text()))
        except ValueError:
            pass

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def load_structure_from_tmm_tab(self):
        layers_widgets = self.tmm_sim.layer_widgets
        reflector_name = self.tmm_sim.combo_reflector.currentText()
        substrate_name = self.tmm_sim.combo_substrate.currentText()
        try:
            reflector_thick_nm = float(self.tmm_sim.edit_reflector_thick.text())
        except ValueError:
            QMessageBox.warning(self, self.tr("加载失败", "Load Failed"), self.tr("TMM 页面中的反射层厚度无效。", "The reflector thickness in the TMM tab is invalid."))
            return
        if not layers_widgets:
            QMessageBox.warning(self, self.tr("加载失败", "Load Failed"), self.tr("TMM 页面中没有功能层。", "There are no functional layers in the TMM tab."))
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
                    self.tr(f"TMM 页面中层 {mat_name} 的厚度无效。", f"The thickness of layer {mat_name} in the TMM tab is invalid."),
                )
                return
            self.base_structure_layers.append({"name": mat_name, "d_nm": thick_nm})
            self.base_structure_str += f"L{layer_index}: {mat_name} ({thick_nm}nm) / "

        self.base_reflector = {"name": reflector_name, "d_nm": reflector_thick_nm}
        self.base_substrate = {"name": substrate_name, "d_nm": np.inf}
        self.base_structure_str += f"{reflector_name}({reflector_thick_nm}nm) / {substrate_name}"

        self._clear_layout(self.fn1_slider_layout)
        self.fn1_slider_widgets.clear()
        self.combo_scan_layer.clear()
        self.fn3_combo_layer_x.clear()
        self.fn3_combo_layer_y.clear()

        for i, layer in enumerate(self.base_structure_layers):
            layer_name = f"L{i + 1}: {layer['name']}"
            d_nm = layer["d_nm"]
            slider_control = _LayerSliderControl(layer_name, d_nm, language=self.language)
            slider_control.sliderReleased.connect(self._fn1_update_spectrum)
            self.fn1_slider_layout.addWidget(slider_control)
            self.fn1_slider_widgets.append(slider_control)

            combo_text = f"{layer_name} ({d_nm}nm)"
            self.combo_scan_layer.addItem(combo_text, i)
            self.fn3_combo_layer_x.addItem(combo_text, i)
            self.fn3_combo_layer_y.addItem(combo_text, i)

        if len(self.base_structure_layers) > 1:
            self.fn3_combo_layer_y.setCurrentIndex(1)

        self.lbl_loaded_structure.setText(self.tr("已加载: ", "Loaded: ") + self.base_structure_str)
        self.combo_scan_layer.setEnabled(True)
        self.fn3_combo_layer_x.setEnabled(True)
        self.fn3_combo_layer_y.setEnabled(True)
        self._fn1_update_spectrum()

    def get_interpolated_stack_for_sweep(self):
        materials_to_load = [layer["name"] for layer in self.base_structure_layers]
        materials_to_load.append(self.base_reflector["name"])
        materials_to_load.append(self.base_substrate["name"])
        return self.material_manager.get_interpolated_stack(
            list(set(materials_to_load)),
            self.lambda_grid_um,
            interp_method="pchip",
        )

    def _fn1_update_spectrum(self):
        if not self.fn1_slider_widgets:
            return
        try:
            interpolated_stack = self.get_interpolated_stack_for_sweep()
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("计算错误", "Calculation Error"),
                self.tr(f"插值材料失败: {e}", f"Failed to interpolate materials: {e}"),
            )
            return

        layer_stack_def = []
        for i, slider_widget in enumerate(self.fn1_slider_widgets):
            mat_name = self.base_structure_layers[i]["name"]
            d_nm = slider_widget.get_value_nm()
            if d_nm > MAX_THICKNESS_NM:
                QMessageBox.warning(
                    self,
                    self.tr("范围错误", "Range Error"),
                    self.tr(
                        f"层 {mat_name} 的厚度 {d_nm}nm 不能超过 {MAX_THICKNESS_NM} nm。",
                        f"The thickness of layer {mat_name} ({d_nm} nm) cannot exceed {MAX_THICKNESS_NM} nm.",
                    ),
                )
                return
            layer_stack_def.append({"n": interpolated_stack[mat_name], "d": d_nm * 1e-9})

        layer_stack_def.append({"n": interpolated_stack[self.base_reflector["name"]], "d": self.base_reflector["d_nm"] * 1e-9})
        layer_stack_def.append({"n": interpolated_stack[self.base_substrate["name"]], "d": np.inf})

        R_s, R_p = calculate_TMM_core(layer_stack_def, self.spectral_manager.lambda_m, theta0_deg=0)
        rho_avg = (R_s + R_p) / 2.0
        epsilon_avg = 1.0 - rho_avg

        self.fn1_plot_widget.clear()
        self.fn1_plot_widget.addLegend()
        self.fn1_plot_widget.plot(self.lambda_grid_um, epsilon_avg, pen=pg.mkPen("#DC3545", width=2.5), name=self.tr("发射率 (epsilon)", "Emissivity (epsilon)"))
        self.fn1_plot_widget.plot(self.lambda_grid_um, rho_avg, pen=pg.mkPen("#007BFF", width=2.5), name=self.tr("反射率 (rho)", "Reflectance (rho)"))

    def run_1d_sweep(self, _unused_signal_data=None):
        if not self.base_structure_layers:
            return

        layer_index = self.combo_scan_layer.currentData()
        if layer_index is None:
            if self.combo_scan_layer.count() > 0:
                self.combo_scan_layer.setCurrentIndex(0)
                layer_index = self.combo_scan_layer.currentData()
            else:
                return

        try:
            min_thick = float(self.fn2_txt_min.text())
            max_thick = float(self.fn2_txt_max.text())
            points = int(self.fn2_edit_points.text())
        except ValueError:
            QMessageBox.warning(self, self.tr("输入错误", "Input Error"), self.tr("请输入有效的扫描范围和点数。", "Please enter a valid sweep range and point count."))
            return

        if max_thick > MAX_THICKNESS_NM:
            QMessageBox.warning(self, self.tr("范围错误", "Range Error"), self.tr(f"最大厚度不能超过 {MAX_THICKNESS_NM} nm (100 um)。", f"Maximum thickness cannot exceed {MAX_THICKNESS_NM} nm (100 um)."))
            self.fn2_txt_max.setText(str(MAX_THICKNESS_NM))
            self._fn2_update_max_slider()
            return

        if points < 2 or points > 1000:
            QMessageBox.warning(self, self.tr("输入错误", "Input Error"), self.tr("点数必须在 2 到 1000 之间。", "Point count must be between 2 and 1000."))
            return

        thickness_range_nm = np.linspace(min_thick, max_thick, points)
        results_eps_bar = []
        results_rho_bar = []

        self.fn2_plot_widget.setTitle(self.tr(f"正在扫描: {self.combo_scan_layer.currentText()}...", f"Scanning: {self.combo_scan_layer.currentText()}..."))
        QApplication.processEvents()

        try:
            interpolated_stack = self.get_interpolated_stack_for_sweep()
            for thick_nm in thickness_range_nm:
                layer_stack_def = []
                for i, layer in enumerate(self.base_structure_layers):
                    mat_name = layer["name"]
                    d_m = (thick_nm if i == layer_index else layer["d_nm"]) * 1e-9
                    layer_stack_def.append({"n": interpolated_stack[mat_name], "d": d_m})

                layer_stack_def.append({"n": interpolated_stack[self.base_reflector["name"]], "d": self.base_reflector["d_nm"] * 1e-9})
                layer_stack_def.append({"n": interpolated_stack[self.base_substrate["name"]], "d": np.inf})

                R_s, R_p = calculate_TMM_core(layer_stack_def, self.spectral_manager.lambda_m, theta0_deg=0)
                rho_avg = (R_s + R_p) / 2.0
                epsilon_avg = 1.0 - rho_avg
                epsilon_bar, rho_bar = calculate_weighted_averages(epsilon_avg, rho_avg, self.spectral_manager)
                results_eps_bar.append(epsilon_bar)
                results_rho_bar.append(rho_bar)
        except Exception as e:
            QMessageBox.critical(self, self.tr("计算错误", "Calculation Error"), self.tr(f"扫描失败: {e}", f"Sweep failed: {e}"))
            self.fn2_plot_widget.setTitle(self.tr(f"扫描失败: {e}", f"Sweep failed: {e}"))
            return

        self.fn2_plot_widget.clear()
        self.fn2_plot_widget.addLegend()
        self.fn2_plot_widget.setTitle(self.tr("加权性能 (Eps_bar / Rho_bar) vs 厚度", "Weighted Performance (Eps_bar / Rho_bar) vs Thickness"))
        self.fn2_plot_widget.plot(thickness_range_nm, results_eps_bar, pen=pg.mkPen("#DC3545", width=2.5), name="Eps_bar")
        self.fn2_plot_widget.plot(thickness_range_nm, results_rho_bar, pen=pg.mkPen("#007BFF", width=2.5), name="Rho_bar")

    def run_2d_sweep(self, _unused_signal_data=None):
        if not self.base_structure_layers:
            QMessageBox.warning(self, self.tr("错误", "Error"), self.tr("请先加载 TMM 结构。", "Please load a TMM structure first."))
            return

        idx_x = self.fn3_combo_layer_x.currentData()
        idx_y = self.fn3_combo_layer_y.currentData()

        if idx_x is None or idx_y is None:
            if self.fn3_combo_layer_x.count() == 0:
                QMessageBox.warning(self, self.tr("错误", "Error"), self.tr("请先加载 TMM 结构。", "Please load a TMM structure first."))
                return
            if idx_x is None:
                idx_x = 0
            if idx_y is None:
                idx_y = 1 if self.fn3_combo_layer_y.count() > 1 else 0

        if idx_x == idx_y:
            QMessageBox.warning(self, self.tr("选择错误", "Selection Error"), self.tr("扫描层 X 和 Y 必须是不同的层。", "Sweep layers X and Y must be different."))
            return

        try:
            x_min = float(self.fn3_txt_x_min.text())
            x_max = float(self.fn3_txt_x_max.text())
            y_min = float(self.fn3_txt_y_min.text())
            y_max = float(self.fn3_txt_y_max.text())
            x_pts = int(self.fn3_edit_points_x.text())
            y_pts = int(self.fn3_edit_points_y.text())
            output_type = self.fn3_combo_output.currentText()
        except ValueError:
            QMessageBox.warning(self, self.tr("输入错误", "Input Error"), self.tr("请输入有效的扫描范围和点数。", "Please enter a valid sweep range and point count."))
            return

        if x_max > MAX_THICKNESS_NM or y_max > MAX_THICKNESS_NM:
            QMessageBox.warning(self, self.tr("范围错误", "Range Error"), self.tr(f"最大厚度不能超过 {MAX_THICKNESS_NM} nm (100 um)。", f"Maximum thickness cannot exceed {MAX_THICKNESS_NM} nm (100 um)."))
            if x_max > MAX_THICKNESS_NM:
                self.fn3_txt_x_max.setText(str(MAX_THICKNESS_NM))
            if y_max > MAX_THICKNESS_NM:
                self.fn3_txt_y_max.setText(str(MAX_THICKNESS_NM))
            return

        if not (2 <= x_pts <= 100) or not (2 <= y_pts <= 100):
            QMessageBox.warning(self, self.tr("输入错误", "Input Error"), self.tr("点数 (X 和 Y) 必须在 2 到 100 之间。", "Point counts (X and Y) must be between 2 and 100."))
            if not (2 <= x_pts <= 100):
                self.fn3_edit_points_x.setText("30")
            if not (2 <= y_pts <= 100):
                self.fn3_edit_points_y.setText("30")
            return

        x_range = np.linspace(x_min, x_max, x_pts)
        y_range = np.linspace(y_min, y_max, y_pts)
        results_matrix = np.zeros((y_pts, x_pts))

        self.fn3_plot_widget.setTitle(self.tr(f"正在扫描 ({x_pts} x {y_pts} = {x_pts * y_pts} 点)...", f"Scanning ({x_pts} x {y_pts} = {x_pts * y_pts} points)..."))
        QApplication.processEvents()

        try:
            interpolated_stack = self.get_interpolated_stack_for_sweep()
            for j, y_thick_nm in enumerate(y_range):
                for i, x_thick_nm in enumerate(x_range):
                    layer_stack_def = []
                    for k, layer in enumerate(self.base_structure_layers):
                        mat_name = layer["name"]
                        if k == idx_x:
                            d_m = x_thick_nm * 1e-9
                        elif k == idx_y:
                            d_m = y_thick_nm * 1e-9
                        else:
                            d_m = layer["d_nm"] * 1e-9
                        layer_stack_def.append({"n": interpolated_stack[mat_name], "d": d_m})

                    layer_stack_def.append({"n": interpolated_stack[self.base_reflector["name"]], "d": self.base_reflector["d_nm"] * 1e-9})
                    layer_stack_def.append({"n": interpolated_stack[self.base_substrate["name"]], "d": np.inf})

                    R_s, R_p = calculate_TMM_core(layer_stack_def, self.spectral_manager.lambda_m, theta0_deg=0)
                    rho_avg = (R_s + R_p) / 2.0
                    epsilon_avg = 1.0 - rho_avg
                    epsilon_bar, rho_bar = calculate_weighted_averages(epsilon_avg, rho_avg, self.spectral_manager)

                    if "Eps_bar" in output_type:
                        results_matrix[j, i] = epsilon_bar
                    else:
                        results_matrix[j, i] = rho_bar
        except Exception as e:
            QMessageBox.critical(self, self.tr("计算错误", "Calculation Error"), self.tr(f"2D 扫描失败: {e}", f"2D sweep failed: {e}"))
            self.fn3_plot_widget.setTitle(self.tr(f"扫描失败: {e}", f"Sweep failed: {e}"))
            return

        title = self.tr(
            f"2D 热力图: Y={self.fn3_combo_layer_y.currentText()} vs X={self.fn3_combo_layer_x.currentText()}",
            f"2D Heatmap: Y={self.fn3_combo_layer_y.currentText()} vs X={self.fn3_combo_layer_x.currentText()}",
        )
        self.fn3_plot_widget.setTitle(title)
        self.fn3_image_item.setImage(results_matrix.T)

        x_width = x_max - x_min
        y_width = y_max - y_min
        if x_width <= 0:
            x_width = 1.0
        if y_width <= 0:
            y_width = 1.0

        rect = pg.QtCore.QRectF(x_min, y_min, x_width, y_width)
        self.fn3_image_item.setRect(rect)

        min_val = np.min(results_matrix)
        max_val = np.max(results_matrix)
        self.fn3_hist_lut.setLevels(min_val, max_val)
        self.fn3_hist_lut.autoHistogramRange()

        self.fn3_plot_widget.setLabel("bottom", self.tr(f"层 X: {self.fn3_combo_layer_x.currentText()} (nm)", f"Layer X: {self.fn3_combo_layer_x.currentText()} (nm)"))
        self.fn3_plot_widget.setLabel("left", self.tr(f"层 Y: {self.fn3_combo_layer_y.currentText()} (nm)", f"Layer Y: {self.fn3_combo_layer_y.currentText()} (nm)"))
        self.fn3_plot_widget.autoRange()
