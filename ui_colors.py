"""MediaBUDA — Esquema de cores baseado no TradutorBUDA (UIColors.java)."""


# ===== CORES DE FUNDO PRINCIPAIS =====
MAIN_BLUE = "#88A9CC"           # Fundo principal
LIGHT_BLUE = "#A8C4DC"          # Painéis/grupos
SLATE_BLUE = "#5A7A9A"          # Botões
DARK_BLUE = "#3E7EBE"           # Botões de navegação

# ===== CORES DOURADAS/BEGE =====
GOLDEN_KHAKI = "#F0E68C"        # Fundos de seção
LIGHT_BEIGE = "#F5F5DC"         # Campos de entrada
DARK_GOLDENROD = "#B8860B"      # Bordas/acentos

# ===== CORES DE TEXTO =====
TEXT_DARK = "#2C3E50"            # Texto primário
TEXT_MEDIUM = "#4A5A6A"          # Texto secundário

# ===== CORES DE BOTÃO =====
BUTTON_GREEN = "#4CAF50"
BUTTON_RED = "#D16A5F"
BUTTON_PURPLE = "#7F5DA3"


def get_stylesheet() -> str:
    """Retorna a folha de estilo QSS global do MediaBUDA."""
    return f"""
    /* ── Fundo da janela ── */
    QMainWindow {{
        background-color: {MAIN_BLUE};
    }}
    QWidget {{
        color: {TEXT_DARK};
        font-size: 12px;
    }}

    /* ── QGroupBox ── */
    QGroupBox {{
        background-color: {LIGHT_BLUE};
        border: 2px solid {DARK_GOLDENROD};
        border-radius: 6px;
        margin-top: 10px;
        padding: 6px 4px 4px 4px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 1px 6px;
        color: {TEXT_DARK};
    }}

    /* ── QPushButton ── */
    QPushButton {{
        background-color: {SLATE_BLUE};
        color: white;
        border: 1px solid {DARK_GOLDENROD};
        border-radius: 4px;
        padding: 2px 8px;
        min-height: 18px;
        font-size: 11px;
    }}
    QPushButton:hover {{
        background-color: {DARK_BLUE};
    }}
    QPushButton:pressed {{
        background-color: #2E5E8E;
    }}
    QPushButton:disabled {{
        background-color: #8899AA;
        color: #CCCCCC;
    }}

    /* ── QLineEdit ── */
    QLineEdit {{
        background-color: {LIGHT_BEIGE};
        border: 1px solid {DARK_GOLDENROD};
        border-radius: 3px;
        padding: 2px 4px;
        min-height: 18px;
        color: {TEXT_DARK};
    }}
    QLineEdit:focus {{
        border: 2px solid {DARK_BLUE};
    }}

    /* ── QComboBox ── */
    QComboBox {{
        background-color: {LIGHT_BEIGE};
        border: 1px solid {DARK_GOLDENROD};
        border-radius: 3px;
        padding: 2px 4px;
        min-height: 18px;
        color: {TEXT_DARK};
    }}
    QComboBox::drop-down {{
        border-left: 1px solid {DARK_GOLDENROD};
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {LIGHT_BEIGE};
        border: 1px solid {DARK_GOLDENROD};
        selection-background-color: {SLATE_BLUE};
        selection-color: white;
    }}

    /* ── QTabWidget ── */
    QTabWidget::pane {{
        border: 2px solid {DARK_GOLDENROD};
        border-radius: 4px;
        background-color: {LIGHT_BLUE};
    }}
    QTabBar::tab {{
        background-color: {LIGHT_BLUE};
        border: 1px solid {DARK_GOLDENROD};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 3px 8px;
        margin-right: 1px;
        color: {TEXT_DARK};
        font-size: 11px;
    }}
    QTabBar::tab:selected {{
        background-color: {SLATE_BLUE};
        color: white;
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {DARK_BLUE};
        color: white;
    }}

    /* ── QProgressBar ── */
    QProgressBar {{
        border: 1px solid {DARK_GOLDENROD};
        border-radius: 4px;
        text-align: center;
        background-color: {LIGHT_BEIGE};
        color: {TEXT_DARK};
    }}
    QProgressBar::chunk {{
        background-color: {BUTTON_GREEN};
        border-radius: 3px;
    }}

    /* ── QTextEdit (log) ── */
    QTextEdit {{
        background-color: #1a1a2e;
        color: #E0E0E0;
        border: 1px solid {DARK_GOLDENROD};
        border-radius: 4px;
        font-family: Consolas, monospace;
        font-size: 12px;
    }}

    /* ── QTableWidget ── */
    QTableWidget {{
        background-color: {LIGHT_BEIGE};
        alternate-background-color: #E8E8D0;
        border: 1px solid {DARK_GOLDENROD};
        border-radius: 4px;
        gridline-color: {DARK_GOLDENROD};
        color: {TEXT_DARK};
    }}
    QTableWidget::item:selected {{
        background-color: {SLATE_BLUE};
        color: white;
    }}
    QHeaderView::section {{
        background-color: {SLATE_BLUE};
        color: white;
        padding: 4px;
        border: 1px solid {DARK_GOLDENROD};
        font-weight: bold;
    }}

    /* ── QSlider ── */
    QSlider::groove:horizontal {{
        border: 1px solid {DARK_GOLDENROD};
        height: 6px;
        background: {GOLDEN_KHAKI};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {DARK_BLUE};
        border: 1px solid {DARK_GOLDENROD};
        width: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background: #2E6EAE;
    }}

    /* ── QLabel ── */
    QLabel {{
        color: {TEXT_DARK};
        background: transparent;
    }}

    /* ── QSpinBox ── */
    QSpinBox {{
        background-color: {LIGHT_BEIGE};
        border: 1px solid {DARK_GOLDENROD};
        border-radius: 3px;
        padding: 1px 3px;
        min-height: 18px;
        color: {TEXT_DARK};
    }}

    /* ── QMenuBar ── */
    QMenuBar {{
        background-color: {SLATE_BLUE};
        color: white;
    }}
    QMenuBar::item:selected {{
        background-color: {DARK_BLUE};
    }}
    QMenu {{
        background-color: {LIGHT_BEIGE};
        border: 1px solid {DARK_GOLDENROD};
        color: {TEXT_DARK};
    }}
    QMenu::item:selected {{
        background-color: {SLATE_BLUE};
        color: white;
    }}

    /* ── QCheckBox / QRadioButton ── */
    QCheckBox, QRadioButton {{
        color: {TEXT_DARK};
        spacing: 6px;
    }}

    /* ── QListWidget ── */
    QListWidget {{
        background-color: {LIGHT_BEIGE};
        border: 1px solid {DARK_GOLDENROD};
        border-radius: 4px;
        color: {TEXT_DARK};
    }}
    QListWidget::item:selected {{
        background-color: {SLATE_BLUE};
        color: white;
    }}

    /* ── QSplitter ── */
    QSplitter::handle {{
        background-color: {DARK_GOLDENROD};
        width: 3px;
    }}

    /* ── QFormLayout labels ── */
    QFormLayout QLabel {{
        color: {TEXT_MEDIUM};
        font-weight: bold;
    }}
    """
