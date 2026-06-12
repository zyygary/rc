from typing import List, Optional

import numpy as np
import pyqtgraph as pg
from PySide2.QtWidgets import QMessageBox, QWidget

from core.constants import LAMBDA_GRID_UM, LAMBDA_MIN_UM
from core.spectral_manager import SpectralDataManager
from core.tmm_core import calculate_TMM_core
from core.utils import calculate_weighted_averages, parse_input_string
from ui.i18n import LANGUAGE_EN, normalize_language, tr
from ui.layer_widget import LayerWidget
from ui.tmm_simulator_layout import Ui_TmmSimulatorLayout


class TmmSimulatorWidget(QWidget):
    def __init__(self, material_manager, spectral_manager, parent=None, language="zh"):
        super().__init__(parent)

        self.language = normalize_language(language)
        self.material_manager = material_manager
        self.spectral_manager = spectral_manager
        self.available_mats = self.material_manager.available_materials
        self.lambda_grid_um = LAMBDA_GRID_UM

        self.layer_widgets: List[LayerWidget] = []
        self.last_plot_data: Optional[dict] = None
        self.current_plot_text_items = []

        self.ui = Ui_TmmSimulatorLayout()
        self.ui.setup_ui(self, self.available_mats, language=self.language)

        self.btn_add_layer_top.clicked.connect(self.add_layer_top)
        self.btn_add_layer_bottom.clicked.connect(self.add_layer_bottom)
        self.btn_calculate.clicked.connect(self.on_calculate)
        self.btn_parse_string.clicked.connect(self.on_parse_string)
        self.txt_angle.returnPressed.connect(self.on_calculate)
        self.combo_pol.currentTextChanged.connect(self.on_calculate_or_redraw)

        self.chk_show_solar.toggled.connect(self.update_plot_appearance)
        self.chk_show_atm.toggled.connect(self.update_plot_appearance)
        self.chk_show_rho.toggled.connect(self.update_plot_appearance)
        self.chk_show_epsilon.toggled.connect(self.update_plot_appearance)

        self.add_layer_bottom(mat="PMMA", thick="1068")
        self.add_layer_bottom(mat="SiO2", thick="6749")
        self.add_layer_bottom(mat="TiO2", thick="4675")

        self.set_language(self.language)
        self.on_calculate()

    def tr(self, zh_text: str, en_text: str) -> str:
        return tr(self.language, zh_text, en_text)

    def _message(self, level: str, title_zh: str, title_en: str, text_zh: str, text_en: str):
        title = self.tr(title_zh, title_en)
        text = self.tr(text_zh, text_en)
        if level == "warning":
            QMessageBox.warning(self, title, text)
        elif level == "critical":
            QMessageBox.critical(self, title, text)
        else:
            QMessageBox.information(self, title, text)

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

    def _set_result_labels(self, pol_label="Avg", eps_value=None, rho_value=None):
        if eps_value is None:
            self.lbl_epsilon.setText(
                self.tr("加权发射率", "Weighted Emissivity") + f" (Eps_bar) = --"
            )
        else:
            self.lbl_epsilon.setText(f"Eps_bar ({pol_label}) = {eps_value:.6f}")

        if rho_value is None:
            self.lbl_rho.setText(
                self.tr("加权反射率", "Weighted Reflectance") + f" (Rho_bar) = --"
            )
        else:
            self.lbl_rho.setText(f"Rho_bar ({pol_label}) = {rho_value:.6f}")

    def set_language(self, language):
        self.language = normalize_language(language)

        self.parser_group.setTitle(self.tr("字符串快速导入", "Quick Structure Import"))
        self.btn_parse_string.setText(self.tr("解析并加载结构", "Parse and Load Structure"))
        self.btn_add_layer_top.setText(self.tr("顶部+", "Add Top Layer"))
        self.btn_add_layer_bottom.setText(self.tr("底部+", "Add Bottom Layer"))
        self.lbl_reflector.setText(self.tr("反射层:", "Reflector:"))
        self.lbl_substrate.setText(self.tr("基底:", "Substrate:"))
        self.lbl_angle.setText(self.tr("入射角 (deg):", "Incident Angle (deg):"))
        self.lbl_pol.setText(self.tr("偏振:", "Polarization:"))
        self.chk_show_solar.setText(self.tr("显示太阳光谱", "Show Solar Spectrum"))
        self.chk_show_atm.setText(self.tr("显示大气窗口", "Show Atmospheric Window"))
        self.chk_show_rho.setText(self.tr("显示反射率", "Show Reflectance"))
        self.chk_show_epsilon.setText(self.tr("显示发射率", "Show Emissivity"))
        self.btn_calculate.setText(self.tr("开始计算", "Run Calculation"))
        self.lbl_results_title.setText(self.tr("计算结果:", "Results:"))

        current_index = self.combo_pol.currentIndex()
        self.combo_pol.blockSignals(True)
        self.combo_pol.clear()
        self.combo_pol.addItems(self._polarization_items())
        self.combo_pol.setCurrentIndex(max(current_index, 0))
        self.combo_pol.blockSignals(False)

        for layer_widget in self.layer_widgets:
            layer_widget.set_language(self.language)

        if self.last_plot_data:
            self.update_plot_appearance()
        else:
            self._set_result_labels()
            self.plot_widget.setTitle(self.tr("光谱响应", "Spectral Response"))
            self.plot_widget.setLabel("bottom", self.tr("波长 (um)", "Wavelength (um)"))
            self.plot_widget.setLabel("left", self.tr("归一化强度 / 光学响应", "Normalized Intensity / Optical Response"))

    def update_material_combos(self, new_list: List, new_name: str):
        self.available_mats = new_list

        self.combo_reflector.clear()
        self.combo_reflector.addItems(new_list)
        self.combo_reflector.setCurrentText("Ag")

        self.combo_substrate.clear()
        self.combo_substrate.addItems(new_list)
        self.combo_substrate.setCurrentText("Si")

        for layer_widget in self.layer_widgets:
            current_mat = layer_widget.combo_material.currentText()
            layer_widget.combo_material.clear()
            layer_widget.combo_material.addItems(new_list)
            if current_mat in new_list:
                layer_widget.combo_material.setCurrentText(current_mat)
            elif new_name in new_list:
                layer_widget.combo_material.setCurrentText(new_name)

    def add_layer_top(self):
        new_layer = LayerWidget(self.available_mats, language=self.language)
        new_layer.btn_remove.clicked.connect(lambda: self.remove_layer(new_layer))
        new_layer.btn_add_above.clicked.connect(lambda: self.add_layer_relative(new_layer, 0))
        new_layer.btn_add_below.clicked.connect(lambda: self.add_layer_relative(new_layer, 1))
        self.layers_layout.insertWidget(0, new_layer)
        self.layer_widgets.insert(0, new_layer)

    def add_layer_bottom(self, mat: str = None, thick: str = None):
        new_layer = LayerWidget(self.available_mats, language=self.language)
        if mat and mat in self.available_mats:
            new_layer.combo_material.setCurrentText(mat)
        if thick:
            new_layer.edit_thickness.setText(thick)
        new_layer.btn_remove.clicked.connect(lambda: self.remove_layer(new_layer))
        new_layer.btn_add_above.clicked.connect(lambda: self.add_layer_relative(new_layer, 0))
        new_layer.btn_add_below.clicked.connect(lambda: self.add_layer_relative(new_layer, 1))
        self.layers_layout.addWidget(new_layer)
        self.layer_widgets.append(new_layer)

    def remove_layer(self, layer_widget: LayerWidget):
        self.layers_layout.removeWidget(layer_widget)
        self.layer_widgets.remove(layer_widget)
        layer_widget.deleteLater()

    def _clear_all_layers(self):
        for layer_widget in reversed(self.layer_widgets):
            self.remove_layer(layer_widget)

    def add_layer_relative(self, relative_widget: LayerWidget, offset: int):
        try:
            index = self.layer_widgets.index(relative_widget)
        except ValueError:
            return

        insert_index = index + offset
        new_layer = LayerWidget(self.available_mats, language=self.language)
        new_layer.btn_remove.clicked.connect(lambda: self.remove_layer(new_layer))
        new_layer.btn_add_above.clicked.connect(lambda: self.add_layer_relative(new_layer, 0))
        new_layer.btn_add_below.clicked.connect(lambda: self.add_layer_relative(new_layer, 1))
        self.layers_layout.insertWidget(insert_index, new_layer)
        self.layer_widgets.insert(insert_index, new_layer)

    def plot_spectrum(
        self,
        lambda_um,
        rho_spectrum,
        epsilon_spectrum,
        spectral_manager: SpectralDataManager,
        show_solar: bool,
        show_atm: bool,
        show_rho: bool,
        show_epsilon: bool,
    ):
        spec = spectral_manager

        if self.plot_widget:
            self.plot_layout.removeWidget(self.plot_widget)
            self.plot_widget.deleteLater()

        self.plot_widget = pg.PlotWidget()
        self.plot_layout.addWidget(self.plot_widget)
        self.plot_widget.addLegend()
        self.current_plot_text_items = []

        pol_label = self._current_pol_code()

        if show_rho:
            self.plot_widget.plot(
                lambda_um,
                rho_spectrum,
                pen=pg.mkPen("#007BFF", width=2.5),
                name=self.tr("反射率", "Reflectance") + f" ({pol_label})",
            )
        if show_epsilon:
            self.plot_widget.plot(
                lambda_um,
                epsilon_spectrum,
                pen=pg.mkPen("#DC3545", width=2.5),
                name=self.tr("发射率", "Emissivity") + f" ({pol_label})",
            )

        if show_solar:
            fill_solar = pg.FillBetweenItem(
                pg.PlotDataItem(lambda_um, spec.IAM1_5_norm_masked, pen=pg.mkPen(None)),
                pg.PlotDataItem(lambda_um, np.zeros_like(lambda_um), pen=pg.mkPen(None)),
                brush=pg.mkBrush(255, 193, 7, 70),
            )
            self.plot_widget.addItem(fill_solar)
            text_solar = pg.TextItem(self.tr("太阳波段", "Solar Band"), color=(200, 150, 0), anchor=(0.5, 1))
            text_solar.setPos((0.3 + 2.5) / 2.0, 0.95)
            self.plot_widget.addItem(text_solar)
            self.current_plot_text_items.append(text_solar)

        if show_atm:
            fill_bb = pg.FillBetweenItem(
                pg.PlotDataItem(lambda_um, spec.I_bb_norm_masked, pen=pg.mkPen(None)),
                pg.PlotDataItem(lambda_um, np.zeros_like(lambda_um), pen=pg.mkPen(None)),
                brush=pg.mkBrush(23, 162, 184, 70),
            )
            self.plot_widget.addItem(fill_bb)
            text_atm = pg.TextItem(self.tr("大气窗口", "Atmospheric Window"), color=(0, 100, 200), anchor=(0.5, 1))
            text_atm.setPos((8.0 + 13.0) / 2.0, 0.95)
            self.plot_widget.addItem(text_atm)
            self.current_plot_text_items.append(text_atm)

        self.plot_widget.setLabel("bottom", self.tr("波长 (um)", "Wavelength (um)"))
        self.plot_widget.setLabel("left", self.tr("归一化强度 / 光学响应", "Normalized Intensity / Optical Response"))
        self.plot_widget.setTitle(self.tr("光谱响应", "Spectral Response"))
        self.plot_widget.setXRange(LAMBDA_MIN_UM, 13.0)
        self.plot_widget.setYRange(0, 1)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

    def on_parse_string(self):
        raw_str = self.txt_parse_string.text()
        if not raw_str:
            self._message("warning", "输入错误", "Input Error", "字符串不能为空。", "The input string cannot be empty.")
            return

        try:
            mats, thicks_nm = parse_input_string(raw_str)

            for mat in mats:
                if mat not in self.available_mats:
                    raise ValueError(
                        self.tr(f"材料 '{mat}' 不在数据库中。", f"Material '{mat}' is not in the database.")
                    )

            self._clear_all_layers()
            for mat_name, thick_val in zip(mats, thicks_nm):
                self.add_layer_bottom(mat=mat_name, thick=str(thick_val))

            self.on_calculate()

        except ValueError as e:
            self._message("warning", "解析错误", "Parse Error", str(e), str(e))
        except Exception as e:
            self._message("critical", "解析失败", "Parse Failed", f"发生意外错误: {e}", f"An unexpected error occurred: {e}")

    def on_calculate_or_redraw(self, _=None):
        if not self.last_plot_data:
            self.on_calculate()
            return

        try:
            current_angle = float(self.txt_angle.text())
        except ValueError:
            current_angle = 0.0

        if abs(current_angle - self.last_plot_data.get("angle", 0.0)) > 1e-6:
            self.on_calculate()
        else:
            self.update_plot_appearance()

    def on_calculate(self, _=None):
        try:
            materials_input = []
            thickness_nm = []
            structure_str_for_title = ""

            if len(self.layer_widgets) == 0:
                raise ValueError(self.tr("请至少添加一个功能层。", "Please add at least one functional layer."))

            for layer in self.layer_widgets:
                mat_name = layer.combo_material.currentText()
                thick_str = layer.edit_thickness.text()
                if not thick_str:
                    raise ValueError(self.tr("厚度不能为空。", "Thickness cannot be empty."))
                try:
                    thick_nm_val = float(thick_str)
                except ValueError:
                    raise ValueError(self.tr(f"厚度 '{thick_str}' 不是有效数字。", f"Thickness '{thick_str}' is not a valid number."))

                if mat_name not in self.available_mats:
                    raise ValueError(self.tr(f"材料 '{mat_name}' 不在数据库中。", f"Material '{mat_name}' is not in the database."))

                materials_input.append(mat_name)
                thickness_nm.append(thick_nm_val)
                structure_str_for_title += f"{mat_name}({thick_nm_val:.0f}nm) / "

            thickness_m = np.array(thickness_nm) * 1e-9

            reflector_name = self.combo_reflector.currentText()
            substrate_name = self.combo_substrate.currentText()
            try:
                reflector_d_m = float(self.edit_reflector_thick.text()) * 1e-9
            except ValueError:
                raise ValueError(
                    self.tr(
                        f"反射层厚度 '{self.edit_reflector_thick.text()}' 不是有效数字。",
                        f"Reflector thickness '{self.edit_reflector_thick.text()}' is not a valid number.",
                    )
                )

            try:
                theta0_deg = float(self.txt_angle.text())
            except ValueError:
                theta0_deg = 0.0
                self.txt_angle.setText("0")

            materials_to_load = materials_input + [reflector_name, substrate_name]
            interpolated_stack = self.material_manager.get_interpolated_stack(
                materials_to_load,
                self.lambda_grid_um,
                interp_method="pchip",
            )

            layer_stack_def = []
            for i in range(len(materials_input)):
                mat_name = materials_input[i]
                d_m = thickness_m[i]
                layer_stack_def.append({"n": interpolated_stack[mat_name], "d": d_m})

            layer_stack_def.append({"n": interpolated_stack[reflector_name], "d": reflector_d_m})
            layer_stack_def.append({"n": interpolated_stack[substrate_name], "d": np.inf})

            structure_str_for_title += f"{reflector_name}({reflector_d_m * 1e9:.0f}nm) / {substrate_name}"

            R_s, R_p = calculate_TMM_core(
                layer_stack_def,
                self.spectral_manager.lambda_m,
                theta0_deg=theta0_deg,
            )

            E_s = 1.0 - R_s
            E_p = 1.0 - R_p
            R_avg = (R_s + R_p) / 2.0
            E_avg = (E_s + E_p) / 2.0

            eps_bar_s, rho_bar_s = calculate_weighted_averages(E_s, R_s, self.spectral_manager)
            eps_bar_p, rho_bar_p = calculate_weighted_averages(E_p, R_p, self.spectral_manager)
            eps_bar_avg, rho_bar_avg = calculate_weighted_averages(E_avg, R_avg, self.spectral_manager)

            self.last_plot_data = {
                "lambda_um": self.lambda_grid_um,
                "R_s": R_s,
                "R_p": R_p,
                "R_avg": R_avg,
                "E_s": E_s,
                "E_p": E_p,
                "E_avg": E_avg,
                "eps_bar_s": eps_bar_s,
                "rho_bar_s": rho_bar_s,
                "eps_bar_p": eps_bar_p,
                "rho_bar_p": rho_bar_p,
                "eps_bar_avg": eps_bar_avg,
                "rho_bar_avg": rho_bar_avg,
                "structure_str": structure_str_for_title,
                "angle": theta0_deg,
            }
            self.update_plot_appearance()

        except ValueError as e:
            self._message("warning", "输入错误", "Input Error", str(e), str(e))
        except Exception as e:
            self._message("critical", "计算错误", "Calculation Error", f"发生意外错误: {e}", f"An unexpected error occurred: {e}")

    def update_plot_appearance(self, _checked: bool = None):
        if not self.last_plot_data:
            return

        show_solar = self.chk_show_solar.isChecked()
        show_atm = self.chk_show_atm.isChecked()
        show_rho = self.chk_show_rho.isChecked()
        show_epsilon = self.chk_show_epsilon.isChecked()

        data = self.last_plot_data
        pol_code = self._current_pol_code()

        if pol_code == "S":
            rho_to_plot = data["R_s"]
            eps_to_plot = data["E_s"]
            rho_bar_to_show = data["rho_bar_s"]
            eps_bar_to_show = data["eps_bar_s"]
        elif pol_code == "P":
            rho_to_plot = data["R_p"]
            eps_to_plot = data["E_p"]
            rho_bar_to_show = data["rho_bar_p"]
            eps_bar_to_show = data["eps_bar_p"]
        else:
            rho_to_plot = data["R_avg"]
            eps_to_plot = data["E_avg"]
            rho_bar_to_show = data["rho_bar_avg"]
            eps_bar_to_show = data["eps_bar_avg"]

        self._set_result_labels(pol_code, eps_bar_to_show, rho_bar_to_show)

        self.plot_spectrum(
            data["lambda_um"],
            rho_to_plot,
            eps_to_plot,
            self.spectral_manager,
            show_solar,
            show_atm,
            show_rho,
            show_epsilon,
        )
