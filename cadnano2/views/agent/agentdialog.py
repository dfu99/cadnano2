"""
agentdialog.py

VS Code-style agent dialog overlay for cadnano2.
Provides a text input interface for agentic commands.
"""

import cadnano2.util as util
util.qtWrapImport('QtCore', globals(), [
    'Qt', 'pyqtSignal', 'QSettings', 'QPropertyAnimation', 'QEasingCurve'
])
util.qtWrapImport('QtWidgets', globals(), [
    'QWidget', 'QVBoxLayout', 'QHBoxLayout', 'QLineEdit',
    'QLabel', 'QPushButton', 'QGraphicsDropShadowEffect'
])
util.qtWrapImport('QtGui', globals(), ['QColor'])


class AgentDialog(QWidget):
    """
    Frameless overlay dialog for agent commands.

    Signals:
        commandSubmitted(str): Emitted when user submits a command
        modeChanged(str): Emitted when mode is toggled ('edit' or 'developer')
        dialogClosed(): Emitted when dialog is closed
    """

    commandSubmitted = pyqtSignal(str)
    modeChanged = pyqtSignal(str)
    dialogClosed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "edit"  # Default mode
        self._loadSettings()
        self._setupUI()
        self._setupAnimations()

    def _loadSettings(self):
        """Load persisted settings."""
        settings = QSettings()
        settings.beginGroup("AgentDialog")
        savedMode = settings.value("mode", "edit")
        if savedMode in ("edit", "developer"):
            self._mode = savedMode
        settings.endGroup()

    def _saveSettings(self):
        """Save settings for persistence."""
        settings = QSettings()
        settings.beginGroup("AgentDialog")
        settings.setValue("mode", self._mode)
        settings.endGroup()

    def _setupUI(self):
        """Set up the user interface."""
        # Window flags for frameless overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Fixed width
        self.setFixedWidth(600)

        # Main container with styling
        self._container = QWidget(self)
        self._container.setObjectName("agentContainer")
        self._container.setStyleSheet("""
            #agentContainer {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #d0d0d0;
            }
        """)

        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self._container.setGraphicsEffect(shadow)

        # Container layout
        containerLayout = QVBoxLayout(self._container)
        containerLayout.setContentsMargins(12, 8, 12, 8)
        containerLayout.setSpacing(6)

        # Top row: mode label and toggle button
        topRow = QHBoxLayout()
        topRow.setContentsMargins(0, 0, 0, 0)

        self._modeLabel = QLabel()
        self._modeLabel.setStyleSheet("font-weight: bold; color: #333;")
        self._updateModeLabel()

        self._toggleButton = QPushButton()
        self._toggleButton.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self._updateToggleButton()
        self._toggleButton.clicked.connect(self._onToggleMode)

        topRow.addWidget(self._modeLabel)
        topRow.addStretch()
        topRow.addWidget(self._toggleButton)
        containerLayout.addLayout(topRow)

        # Input field
        self._inputField = QLineEdit()
        self._inputField.setPlaceholderText("Enter a command or describe what you want to do...")
        self._inputField.setStyleSheet("""
            QLineEdit {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                background-color: #fafafa;
            }
            QLineEdit:focus {
                border-color: #0078d4;
                background-color: white;
            }
        """)
        self._inputField.returnPressed.connect(self._onSubmit)
        containerLayout.addWidget(self._inputField)

        # Status label
        self._statusLabel = QLabel("")
        self._statusLabel.setStyleSheet("color: #666; font-size: 11px;")
        self._statusLabel.setWordWrap(True)
        containerLayout.addWidget(self._statusLabel)

        # Main layout for this widget
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(10, 10, 10, 10)  # Margin for shadow
        mainLayout.addWidget(self._container)

        self.adjustSize()

    def _setupAnimations(self):
        """Set up fade animations."""
        self._fadeAnimation = QPropertyAnimation(self, b"windowOpacity")
        self._fadeAnimation.setDuration(150)
        self._fadeAnimation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _updateModeLabel(self):
        """Update the mode label text."""
        if self._mode == "edit":
            self._modeLabel.setText("Edit Mode")
        else:
            self._modeLabel.setText("Developer Mode")

    def _updateToggleButton(self):
        """Update the toggle button text."""
        if self._mode == "edit":
            self._toggleButton.setText("Switch to Dev")
        else:
            self._toggleButton.setText("Switch to Edit")

    def _onToggleMode(self):
        """Handle mode toggle button click."""
        if self._mode == "edit":
            self._mode = "developer"
        else:
            self._mode = "edit"
        self._updateModeLabel()
        self._updateToggleButton()
        self._saveSettings()
        self.modeChanged.emit(self._mode)

    def _onSubmit(self):
        """Handle command submission."""
        command = self._inputField.text().strip()
        if command:
            self.commandSubmitted.emit(command)
            self._inputField.clear()

    def mode(self):
        """Return the current mode."""
        return self._mode

    def setStatus(self, message):
        """Set the status message."""
        self._statusLabel.setText(message)

    def clearStatus(self):
        """Clear the status message."""
        self._statusLabel.setText("")

    def showDialog(self):
        """Show the dialog with fade-in animation."""
        self.setWindowOpacity(0)
        self.show()
        self._fadeAnimation.setStartValue(0)
        self._fadeAnimation.setEndValue(1)
        self._fadeAnimation.start()
        self._inputField.setFocus()

    def hideDialog(self):
        """Hide the dialog with fade-out animation."""
        self._fadeAnimation.setStartValue(1)
        self._fadeAnimation.setEndValue(0)
        self._fadeAnimation.finished.connect(self._onFadeOutFinished)
        self._fadeAnimation.start()

    def _onFadeOutFinished(self):
        """Handle fade-out completion."""
        self._fadeAnimation.finished.disconnect(self._onFadeOutFinished)
        self.hide()
        self.dialogClosed.emit()

    def positionRelativeToParent(self):
        """Position the dialog centered horizontally, 60px from top."""
        parent = self.parent()
        if parent is None:
            return

        parentGeom = parent.geometry()
        dialogWidth = self.width()

        # Center horizontally, 60px from top
        x = (parentGeom.width() - dialogWidth) // 2
        y = 60

        self.move(x, y)

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Escape:
            self.hideDialog()
        else:
            super().keyPressEvent(event)
