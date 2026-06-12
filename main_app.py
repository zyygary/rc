"""Desktop application entry point for the TMM simulation platform."""

import sys

from PySide2.QtCore import QSize
from PySide2.QtWidgets import (
    QAction,
    QApplication,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from core.material_manager import MaterialManager
from core.spectral_manager import SpectralDataManager

import ui.styles as styles
from ui.angle_scan_widget import AngleScanWidget
from ui.cooling_widget import CoolingWidget
from ui.i18n import LANGUAGE_EN, LANGUAGE_ZH, normalize_language
from ui.material_viewer_widget import MaterialViewerWidget
from ui.sweep_widget import SweepWidget
from ui.tmm_simulator_widget import TmmSimulatorWidget


class MainWindow(QMainWindow):
    def __init__(self, language=LANGUAGE_ZH):
        super().__init__()
        self.language = normalize_language(language)

        print("--- (App) Loading TMM engine... ---")
        try:
            self.material_manager = MaterialManager()
            self.material_manager.load_all_materials()
            self.spectral_manager = SpectralDataManager()
        except Exception as e:
            QMessageBox.critical(self, "Startup Error", f"Failed to load TMM engine: {e}")
            sys.exit()

        self.setMinimumSize(QSize(1200, 800))

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.material_viewer_widget = MaterialViewerWidget(
            self.material_manager,
            language=self.language,
        )
        self.tab_widget.addTab(self.material_viewer_widget, "")

        self.tmm_sim_widget = TmmSimulatorWidget(
            self.material_manager,
            self.spectral_manager,
            language=self.language,
        )
        self.tab_widget.addTab(self.tmm_sim_widget, "")

        self.sweep_widget = SweepWidget(
            self.material_manager,
            self.spectral_manager,
            self.tmm_sim_widget,
            language=self.language,
        )
        self.tab_widget.addTab(self.sweep_widget, "")

        self.angle_scan_widget = AngleScanWidget(
            self.material_manager,
            self.spectral_manager,
            self.tmm_sim_widget,
            language=self.language,
        )
        self.tab_widget.addTab(self.angle_scan_widget, "")

        self.cooling_widget = CoolingWidget(
            self.material_manager,
            self.spectral_manager,
            self.tmm_sim_widget,
            language=self.language,
        )
        self.tab_widget.addTab(self.cooling_widget, "")

        self.material_viewer_widget.materialListUpdated.connect(
            self.tmm_sim_widget.update_material_combos
        )
        self.material_viewer_widget.materialListUpdated.connect(
            self.material_viewer_widget.update_self_combos
        )

        self._setup_language_menu()
        self.set_language(self.language)

        print("--- (App) Main window initialized ---")

    def _setup_language_menu(self):
        menu = self.menuBar().addMenu("Language")
        action_zh = QAction("中文", self)
        action_en = QAction("English", self)
        action_zh.triggered.connect(lambda: self.set_language(LANGUAGE_ZH))
        action_en.triggered.connect(lambda: self.set_language(LANGUAGE_EN))
        menu.addAction(action_zh)
        menu.addAction(action_en)

    def set_language(self, language):
        self.language = normalize_language(language)

        self.material_viewer_widget.set_language(self.language)
        self.tmm_sim_widget.set_language(self.language)
        self.sweep_widget.set_language(self.language)
        self.angle_scan_widget.set_language(self.language)
        self.cooling_widget.set_language(self.language)

        if self.language == LANGUAGE_EN:
            self.setWindowTitle("TMM Simulation Platform V6.0")
            tab_labels = [
                "1. Materials Database",
                "2. TMM Spectral Simulation",
                "3. Parameter Sweep",
                "4. Angle Scan",
                "5. Net Cooling Power",
            ]
        else:
            self.setWindowTitle("TMM 仿真平台 V6.0")
            tab_labels = [
                "1. 材料库 (Database)",
                "2. TMM 光谱仿真 (Simulation)",
                "3. 参数扫描 (Sweep)",
                "4. 角度扫描 (Angle)",
                "5. 净冷却功率 (Cooling)",
            ]

        for index, label in enumerate(tab_labels):
            self.tab_widget.setTabText(index, label)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    styles.setup_pyqtgraph_theme()
    app.setStyleSheet(styles.QSS_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
