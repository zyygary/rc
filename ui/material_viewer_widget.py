from typing import List

import pyqtgraph as pg
from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QFileDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.constants import LAMBDA_GRID_UM
from core.material_manager import MaterialManager
from ui.i18n import normalize_language, tr


class MaterialViewerWidget(QWidget):
    materialListUpdated = Signal(list, str)

    def __init__(self, material_manager: MaterialManager, parent=None, language="zh"):
        super().__init__(parent)
        self.language = normalize_language(language)
        self.material_manager = material_manager
        self.available_mats = self.material_manager.available_materials
        self.setup_ui()
        self.set_language(self.language)

    def tr(self, zh_text: str, en_text: str) -> str:
        return tr(self.language, zh_text, en_text)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        selector_layout = QHBoxLayout()
        self.lbl_selector = QLabel()
        selector_layout.addWidget(self.lbl_selector)
        self.combo_material = QComboBox()
        self.combo_material.addItems(self.available_mats)
        selector_layout.addWidget(self.combo_material)

        self.btn_load_material = QPushButton()
        self.btn_load_material.setVisible(False)
        selector_layout.addWidget(self.btn_load_material)
        layout.addLayout(selector_layout)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.legend = None
        layout.addWidget(self.plot_widget)

        add_layout = QHBoxLayout()
        self.btn_add_new = QPushButton()
        self.btn_add_new.setEnabled(True)
        add_layout.addWidget(self.btn_add_new)
        add_layout.addStretch()
        layout.addLayout(add_layout)

        self.combo_material.currentTextChanged.connect(self.plot_n_k)
        self.btn_add_new.clicked.connect(self.on_add_new_material)

        if self.available_mats:
            self.plot_n_k()

    def set_language(self, language):
        self.language = normalize_language(language)
        self.lbl_selector.setText(self.tr("选择材料:", "Select Material:"))
        self.btn_add_new.setText(self.tr("添加新材料 (.txt)", "Add Material (.txt)"))
        self.plot_widget.setTitle(self.tr("材料 N/K 光学常数", "Material Optical Constants (n/k)"))
        self.plot_widget.setLabel("bottom", self.tr("波长 (um)", "Wavelength (um)"))
        self.plot_widget.setLabel("left", self.tr("折射率 (n/k)", "Refractive Index (n/k)"))
        if self.available_mats:
            self.plot_n_k()

    def on_add_new_material(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("选择材料文件", "Select Material File"),
            "",
            self.tr("材料文件 (*.txt)", "Material Files (*.txt)"),
        )

        if not filepath:
            return

        try:
            new_name, new_list = self.material_manager.add_new_material_from_file(filepath)
            self.materialListUpdated.emit(new_list, new_name)
            QMessageBox.information(
                self,
                self.tr("成功", "Success"),
                self.tr(
                    f"成功添加并加载了新材料: {new_name}",
                    f"Successfully added and loaded new material: {new_name}",
                ),
            )
        except (ValueError, IOError) as e:
            QMessageBox.warning(self, self.tr("添加失败", "Add Failed"), str(e))
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("严重错误", "Critical Error"),
                self.tr(f"发生意外错误: {e}", f"An unexpected error occurred: {e}"),
            )

    def update_self_combos(self, new_list: List, new_name: str):
        self.available_mats = new_list
        self.combo_material.clear()
        self.combo_material.addItems(new_list)
        self.combo_material.setCurrentText(new_name)

    def plot_n_k(self):
        mat_name = self.combo_material.currentText()
        if not mat_name:
            self.plot_widget.clear()
            self.plot_widget.setTitle(self.tr("请选择材料", "Please Select a Material"))
            return

        self.plot_widget.clear()
        self.legend = self.plot_widget.addLegend()
        self.legend.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, 10))

        try:
            if mat_name in self.material_manager.raw_data_cache:
                w_raw, n_raw, k_raw = self.material_manager.raw_data_cache[mat_name]

                scatter_n = pg.ScatterPlotItem(
                    x=w_raw,
                    y=n_raw,
                    pen=pg.mkPen(None),
                    brush=pg.mkBrush("#007BFF"),
                    size=5,
                    name=self.tr("n (原始)", "n (Raw)"),
                )
                self.plot_widget.addItem(scatter_n)

                scatter_k = pg.ScatterPlotItem(
                    x=w_raw,
                    y=k_raw,
                    pen=pg.mkPen(None),
                    brush=pg.mkBrush("#DC3545"),
                    size=5,
                    name=self.tr("k (原始)", "k (Raw)"),
                )
                self.plot_widget.addItem(scatter_k)

            interpolated_stack = self.material_manager.get_interpolated_stack(
                [mat_name],
                LAMBDA_GRID_UM,
                interp_method="pchip",
            )
            n_complex = interpolated_stack[mat_name]
            n_fit = n_complex.real.flatten()
            k_fit = n_complex.imag.flatten()

            self.plot_widget.plot(
                LAMBDA_GRID_UM,
                n_fit,
                pen=pg.mkPen("#007BFF", width=2, style=Qt.DashLine),
                name=self.tr("n (拟合)", "n (Fit)"),
            )
            self.plot_widget.plot(
                LAMBDA_GRID_UM,
                k_fit,
                pen=pg.mkPen("#DC3545", width=2, style=Qt.DashLine),
                name=self.tr("k (拟合)", "k (Fit)"),
            )

            self.plot_widget.setTitle(
                self.tr(
                    f"{mat_name} - N/K 光学常数 (点: 原始, 线: 拟合)",
                    f"{mat_name} - Optical Constants (Points: Raw, Lines: Fit)",
                )
            )
            self.plot_widget.autoRange()
            self.plot_widget.setXRange(0, 13)
        except Exception:
            self.plot_widget.setTitle(
                self.tr(
                    f"{mat_name} - 数据加载失败",
                    f"{mat_name} - Failed to Load Data",
                )
            )
