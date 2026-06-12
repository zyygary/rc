import sys

from PySide2.QtWidgets import QApplication

import ui.styles as styles
from main_app import MainWindow
from ui.i18n import LANGUAGE_EN


if __name__ == "__main__":
    app = QApplication(sys.argv)

    styles.setup_pyqtgraph_theme()
    app.setStyleSheet(styles.QSS_STYLESHEET)

    window = MainWindow(language=LANGUAGE_EN)
    window.show()
    sys.exit(app.exec_())
