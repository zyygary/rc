from PySide2.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton

from ui.i18n import tr


class LayerWidget(QFrame):
    combo_material: QComboBox
    edit_thickness: QLineEdit
    btn_remove: QPushButton
    btn_add_above: QPushButton
    btn_add_below: QPushButton

    def __init__(self, material_list, language="zh"):
        super().__init__()
        self.language = language

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.combo_material = QComboBox()
        self.combo_material.addItems(material_list)
        self.layout.addWidget(self.combo_material, 3)

        self.edit_thickness = QLineEdit()
        self.layout.addWidget(self.edit_thickness, 5)

        self.lbl_unit = QLabel("nm")
        self.layout.addWidget(self.lbl_unit)

        self.btn_add_above = QPushButton("+")
        self.btn_add_above.setObjectName("AddAboveButton")
        self.layout.addWidget(self.btn_add_above)

        self.btn_add_below = QPushButton("-")
        self.btn_add_below.setObjectName("AddBelowButton")
        self.layout.addWidget(self.btn_add_below)

        self.btn_remove = QPushButton("x")
        self.btn_remove.setObjectName("RemoveButton")
        self.layout.addWidget(self.btn_remove)

        self.set_language(language)

    def set_language(self, language):
        self.language = language
        self.edit_thickness.setPlaceholderText(tr(self.language, "厚度", "Thickness"))
