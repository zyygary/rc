from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
import pyqtgraph as pg

from ui.i18n import tr


class Ui_TmmSimulatorLayout:
    def setup_ui(self, sim_widget: QWidget, available_mats: list, language="zh"):
        main_layout = QHBoxLayout(sim_widget)

        left_panel_layout = QVBoxLayout()

        parser_group = QGroupBox(
            tr(language, "字符串快速导入", "Quick Structure Import")
        )
        parser_layout = QVBoxLayout()
        sim_widget.txt_parse_string = QLineEdit()
        sim_widget.txt_parse_string.setPlaceholderText("Si3N4 PMMA SiN 91 1317.2 2575.8")
        sim_widget.btn_parse_string = QPushButton(
            tr(language, "解析并加载结构", "Parse and Load Structure")
        )
        parser_layout.addWidget(sim_widget.txt_parse_string)
        parser_layout.addWidget(sim_widget.btn_parse_string)
        parser_group.setLayout(parser_layout)
        left_panel_layout.addWidget(parser_group)
        sim_widget.parser_group = parser_group

        add_layer_layout = QHBoxLayout()
        sim_widget.btn_add_layer_top = QPushButton(tr(language, "顶部+", "Add Top Layer"))
        sim_widget.btn_add_layer_bottom = QPushButton(tr(language, "底部+", "Add Bottom Layer"))
        add_layer_layout.addWidget(sim_widget.btn_add_layer_top)
        add_layer_layout.addWidget(sim_widget.btn_add_layer_bottom)
        left_panel_layout.addLayout(add_layer_layout)

        sim_widget.scroll_area = QScrollArea()
        sim_widget.scroll_area.setWidgetResizable(True)
        sim_widget.scroll_widget = QWidget()
        sim_widget.layers_layout = QVBoxLayout(sim_widget.scroll_widget)
        sim_widget.layers_layout.setAlignment(Qt.AlignTop)
        sim_widget.scroll_area.setWidget(sim_widget.scroll_widget)
        left_panel_layout.addWidget(sim_widget.scroll_area)

        reflector_layout = QHBoxLayout()
        sim_widget.lbl_reflector = QLabel(tr(language, "反射层:", "Reflector:"))
        reflector_layout.addWidget(sim_widget.lbl_reflector)
        sim_widget.combo_reflector = QComboBox()
        sim_widget.combo_reflector.addItems(available_mats)
        sim_widget.combo_reflector.setCurrentText("Ag")
        sim_widget.edit_reflector_thick = QLineEdit("200")
        sim_widget.edit_reflector_thick.setFixedWidth(80)
        reflector_layout.addWidget(sim_widget.combo_reflector)
        reflector_layout.addWidget(sim_widget.edit_reflector_thick)
        reflector_layout.addWidget(QLabel("nm"))

        substrate_layout = QHBoxLayout()
        sim_widget.lbl_substrate = QLabel(tr(language, "基底:", "Substrate:"))
        substrate_layout.addWidget(sim_widget.lbl_substrate)
        sim_widget.combo_substrate = QComboBox()
        sim_widget.combo_substrate.addItems(available_mats)
        sim_widget.combo_substrate.setCurrentText("Si")
        substrate_layout.addWidget(sim_widget.combo_substrate)

        left_panel_layout.addLayout(reflector_layout)
        left_panel_layout.addLayout(substrate_layout)

        physics_layout = QHBoxLayout()
        sim_widget.lbl_angle = QLabel(tr(language, "入射角 (deg):", "Incident Angle (deg):"))
        physics_layout.addWidget(sim_widget.lbl_angle)
        sim_widget.txt_angle = QLineEdit("0")
        sim_widget.txt_angle.setFixedWidth(50)
        physics_layout.addWidget(sim_widget.txt_angle)

        sim_widget.lbl_pol = QLabel(tr(language, "偏振:", "Polarization:"))
        physics_layout.addWidget(sim_widget.lbl_pol)
        sim_widget.combo_pol = QComboBox()
        physics_layout.addWidget(sim_widget.combo_pol, 1)

        left_panel_layout.addLayout(physics_layout)

        options_layout_1 = QHBoxLayout()
        sim_widget.chk_show_solar = QCheckBox(tr(language, "显示太阳光谱", "Show Solar Spectrum"))
        sim_widget.chk_show_solar.setChecked(True)
        sim_widget.chk_show_atm = QCheckBox(tr(language, "显示大气窗口", "Show Atmospheric Window"))
        sim_widget.chk_show_atm.setChecked(True)
        options_layout_1.addWidget(sim_widget.chk_show_solar)
        options_layout_1.addWidget(sim_widget.chk_show_atm)

        options_layout_2 = QHBoxLayout()
        sim_widget.chk_show_rho = QCheckBox(tr(language, "显示反射率", "Show Reflectance"))
        sim_widget.chk_show_rho.setChecked(True)
        sim_widget.chk_show_epsilon = QCheckBox(tr(language, "显示发射率", "Show Emissivity"))
        sim_widget.chk_show_epsilon.setChecked(True)
        options_layout_2.addWidget(sim_widget.chk_show_rho)
        options_layout_2.addWidget(sim_widget.chk_show_epsilon)

        left_panel_layout.addLayout(options_layout_1)
        left_panel_layout.addLayout(options_layout_2)

        sim_widget.btn_calculate = QPushButton(tr(language, "开始计算", "Run Calculation"))
        sim_widget.btn_calculate.setObjectName("CalculateButton")
        left_panel_layout.addWidget(sim_widget.btn_calculate)

        left_widget = QWidget()
        left_widget.setLayout(left_panel_layout)
        left_widget.setFixedWidth(380)
        main_layout.addWidget(left_widget)

        right_panel_layout = QVBoxLayout()

        sim_widget.plot_layout = QVBoxLayout()
        sim_widget.plot_widget = pg.PlotWidget()
        sim_widget.plot_layout.addWidget(sim_widget.plot_widget)
        right_panel_layout.addLayout(sim_widget.plot_layout)

        sim_widget.lbl_results_title = QLabel(tr(language, "计算结果:", "Results:"))
        sim_widget.lbl_results_title.setObjectName("TitleLabel")
        sim_widget.lbl_epsilon = QLabel()
        sim_widget.lbl_epsilon.setObjectName("ResultLabel")
        sim_widget.lbl_rho = QLabel()
        sim_widget.lbl_rho.setObjectName("ResultLabel")

        results_layout = QHBoxLayout()
        results_layout.addWidget(sim_widget.lbl_epsilon)
        results_layout.addWidget(sim_widget.lbl_rho)

        right_panel_layout.addWidget(sim_widget.lbl_results_title)
        right_panel_layout.addLayout(results_layout)

        right_widget = QWidget()
        right_widget.setLayout(right_panel_layout)
        main_layout.addWidget(right_widget)
