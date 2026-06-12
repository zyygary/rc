import pyqtgraph as pg
QSS_STYLESHEET = """
    /* --- 全局 --- */
    QWidget {
        background-color: #FFFFF0; /* 象牙白/浅黄 背景 */
        color: #212529;            /* 深色文字 */
        font-family: "Microsoft YaHei";
        font-size: 10pt;
    }

    /* --- 按钮 --- */
    QPushButton {
        background-color: #007BFF; /* 主题蓝色 */
        color: #FFFFFF;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #0069D9; /* 悬停时变暗 */
    }
    QPushButton:pressed {
        background-color: #0056B3; /* 按下时更暗 */
    }

    /* --- “计算”按钮的特殊样式 --- */
    #CalculateButton {
        background-color: #28A745; /* 绿色 */
        font-size: 12pt;
    }
    #CalculateButton:hover {
        background-color: #218838;
    }
    #CalculateButton:pressed {
        background-color: #1E7E34;
    }

    /* --- [V18 新增] “添加”按钮的样式 (绿色) --- */
    #AddAboveButton {
        background-color: #F8F9FA;
        color: #28A745;            /* 绿色文字 */
        font-weight: bold;
        padding: 6px;
        max-width: 30px;
        border: 1px solid #DEE2E6;
    }
    #AddAboveButton:hover {
        background-color: #E2E6EA;
    }

    /* --- [V18 新增] “添加”按钮的样式 (蓝色) --- */
    #AddBelowButton {
        background-color: #F8F9FA;
        color: #007BFF;            /* 蓝色文字 */
        font-weight: bold;
        padding: 6px;
        max-width: 30px;
        border: 1px solid #DEE2E6;
    }
    #AddBelowButton:hover {
        background-color: #E2E6EA;
    }

    /* --- "删除" 按钮的特殊样式 --- */
    #RemoveButton {
        background-color: #F8F9FA; /* 浅灰色 */
        color: #DC3545;            /* 红色文字 */
        font-weight: bold;
        padding: 6px;
        max-width: 30px;
        border: 1px solid #DEE2E6;
    }
    #RemoveButton:hover {
        background-color: #E2E6EA;
    }

    /* --- 输入框和下拉菜单 --- */
    QLineEdit, QComboBox {
        background-color: #FFFFFF;
        border: 1px solid #CED4DA; /* 灰色边框 */
        border-radius: 4px;
        padding: 5px;
    }
    QComboBox::drop-down {
        border: none;
    }
    QComboBox QAbstractItemView { /* 下拉菜单的弹出列表 */
        background-color: #FFFFFF;
        border: 1px solid #CED4DA;
        selection-background-color: #007BFF;
        selection-color: #FFFFFF;
    }

    /* --- 滚动区域 --- */
    QScrollArea {
        border: 1px solid #DEE2E6;
        border-radius: 4px;
    }
    /* 滚动条样式 */
    QScrollBar:vertical {
        background: #F8F9FA;
        width: 12px;
    }
    QScrollBar::handle:vertical {
        background: #CED4DA;
        min-height: 20px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical:hover {
        background: #ADB5BD;
    }

    /* --- 标签 --- */
    QLabel {
        color: #212529; /* 深色文字 */
        padding-top: 4px;
    }
    #TitleLabel { /* (用于 "计算结果:") */
        font-weight: bold;
        font-size: 14px;
        color: #212529;
    }
    #ResultLabel { /* (用于 Eps_bar 和 Rho_bar) */
        font-size: 11pt;
        color: #212529;
    }

    /* --- 复选框 --- */
    QCheckBox {
        spacing: 5px;
    }
    QCheckBox::indicator {
        width: 13px;
        height: 13px;
    }
    QCheckBox::indicator:unchecked {
        background-color: #FFFFFF;
        border: 1px solid #ADB5BD;
        border-radius: 3px;
    }
    QCheckBox::indicator:checked {
        background-color: #007BFF;
        border: 1px solid #007BFF;
        border-radius: 3px;
    }

    /* --- 层控件的边框 --- */
    QFrame {
        border: 1px solid #DEE2E6;
        border-radius: 4px;
    }
"""

def setup_pyqtgraph_theme():
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('foreground', 'k')
    pg.setConfigOptions(antialias=True)