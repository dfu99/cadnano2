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
    'QLabel', 'QPushButton', 'QGraphicsDropShadowEffect',
    'QScrollArea', 'QTextEdit', 'QSizeGrip', 'QComboBox'
])
util.qtWrapImport('QtGui', globals(), ['QColor'])


class AgentDialog(QWidget):
    """
    Frameless overlay dialog for agent commands.

    Signals:
        commandSubmitted(str): Emitted when user submits a command
        modeChanged(str): Emitted when mode is toggled ('edit' or 'developer')
        backendChanged(str): Emitted when backend is changed ('ollama' or 'openai')
        dialogClosed(): Emitted when dialog is closed
        actionApproved(): Emitted when user approves an action
        actionCorrectionRequested(): Emitted when user wants to reject and correct an action
    """

    commandSubmitted = pyqtSignal(str)
    modeChanged = pyqtSignal(str)
    backendChanged = pyqtSignal(str)
    apiKeySubmitted = pyqtSignal(str)
    dialogClosed = pyqtSignal()
    actionApproved = pyqtSignal()
    actionCorrectionRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "edit"  # Default mode
        self._backend = "ollama"  # Default backend
        self._dragging = False
        self._dragPosition = None
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
        savedBackend = settings.value("backend", "ollama")
        if savedBackend in ("ollama", "openai"):
            self._backend = savedBackend
        settings.endGroup()

    def _saveSettings(self):
        """Save settings for persistence."""
        settings = QSettings()
        settings.beginGroup("AgentDialog")
        settings.setValue("mode", self._mode)
        settings.setValue("backend", self._backend)
        settings.endGroup()

    def _setupUI(self):
        """Set up the user interface."""
        # Window flags for frameless overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Resizable dimensions
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        self.resize(600, 300)

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

        # Title bar for dragging
        self._titleBar = QWidget()
        self._titleBar.setFixedHeight(24)
        self._titleBar.setStyleSheet("background: transparent;")
        titleBarLayout = QHBoxLayout(self._titleBar)
        titleBarLayout.setContentsMargins(0, 0, 0, 0)

        self._modeLabel = QLabel()
        self._modeLabel.setStyleSheet("font-weight: bold; color: #333;")
        self._updateModeLabel()

        # Backend selector
        self._backendSelector = QComboBox()
        self._backendSelector.addItem("Ollama (Local)", "ollama")
        self._backendSelector.addItem("OpenAI API", "openai")
        self._backendSelector.setStyleSheet("""
            QComboBox {
                background-color: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                min-width: 100px;
                color: #333;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #333;
                selection-background-color: #0078d4;
                selection-color: white;
            }
        """)
        # Set current backend
        idx = self._backendSelector.findData(self._backend)
        if idx >= 0:
            self._backendSelector.setCurrentIndex(idx)
        self._backendSelector.currentIndexChanged.connect(self._onBackendChanged)

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

        titleBarLayout.addWidget(self._modeLabel)
        titleBarLayout.addStretch()
        titleBarLayout.addWidget(self._backendSelector)
        titleBarLayout.addWidget(self._toggleButton)
        containerLayout.addWidget(self._titleBar)

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
                color: black;
            }
            QLineEdit:focus {
                border-color: #0078d4;
                background-color: white;
            }
        """)
        self._inputField.returnPressed.connect(self._onSubmit)
        containerLayout.addWidget(self._inputField)

        # Scrollable response area
        self._responseArea = QTextEdit()
        self._responseArea.setReadOnly(True)
        self._responseArea.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
                background-color: #fafafa;
                color: #333;
            }
        """)
        self._responseArea.setPlaceholderText("Agent responses will appear here...")
        containerLayout.addWidget(self._responseArea, 1)  # stretch factor 1

        # Approval buttons row (hidden by default)
        self._approvalRow = QWidget()
        approvalLayout = QHBoxLayout(self._approvalRow)
        approvalLayout.setContentsMargins(0, 4, 0, 4)
        approvalLayout.setSpacing(8)

        self._approvalLabel = QLabel("Action executed. Review in GUI:")
        self._approvalLabel.setStyleSheet("color: #666; font-size: 11px;")

        buttonStyle = """
            QPushButton {
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
        """

        self._approveButton = QPushButton("✓ Approve")
        self._approveButton.setStyleSheet(buttonStyle + """
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self._approveButton.clicked.connect(self._onApprove)

        self._correctButton = QPushButton("✎ Reject && Correct")
        self._correctButton.setStyleSheet(buttonStyle + """
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self._correctButton.clicked.connect(self._onCorrect)

        approvalLayout.addWidget(self._approvalLabel)
        approvalLayout.addStretch()
        approvalLayout.addWidget(self._approveButton)
        approvalLayout.addWidget(self._correctButton)

        self._approvalRow.hide()  # Hidden by default
        containerLayout.addWidget(self._approvalRow)

        # API key input row (hidden by default)
        self._apiKeyRow = QWidget()
        apiKeyLayout = QHBoxLayout(self._apiKeyRow)
        apiKeyLayout.setContentsMargins(0, 4, 0, 4)
        apiKeyLayout.setSpacing(8)

        apiKeyLabel = QLabel("OpenAI API Key:")
        apiKeyLabel.setStyleSheet("color: #666; font-size: 11px;")

        self._apiKeyInput = QLineEdit()
        self._apiKeyInput.setPlaceholderText("sk-...")
        self._apiKeyInput.setEchoMode(QLineEdit.EchoMode.Password)
        self._apiKeyInput.setStyleSheet("""
            QLineEdit {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
                background-color: #fafafa;
                color: black;
            }
            QLineEdit:focus {
                border-color: #0078d4;
                background-color: white;
            }
        """)
        self._apiKeyInput.returnPressed.connect(self._onApiKeySubmit)

        self._apiKeySaveButton = QPushButton("Save")
        self._apiKeySaveButton.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self._apiKeySaveButton.clicked.connect(self._onApiKeySubmit)

        apiKeyLayout.addWidget(apiKeyLabel)
        apiKeyLayout.addWidget(self._apiKeyInput, 1)
        apiKeyLayout.addWidget(self._apiKeySaveButton)

        self._apiKeyRow.hide()
        containerLayout.addWidget(self._apiKeyRow)

        # Bottom row with size grip
        bottomRow = QHBoxLayout()
        bottomRow.setContentsMargins(0, 0, 0, 0)
        bottomRow.addStretch()
        self._sizeGrip = QSizeGrip(self)
        self._sizeGrip.setStyleSheet("background: transparent;")
        bottomRow.addWidget(self._sizeGrip)
        containerLayout.addLayout(bottomRow)

        # Main layout for this widget
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(10, 10, 10, 10)  # Margin for shadow
        mainLayout.addWidget(self._container)

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

    def _onBackendChanged(self, index):
        """Handle backend selection change."""
        self._backend = self._backendSelector.itemData(index)
        self._saveSettings()
        self.backendChanged.emit(self._backend)

    def _onSubmit(self):
        """Handle command submission."""
        command = self._inputField.text().strip()
        if command:
            self.commandSubmitted.emit(command)
            self._inputField.clear()

    def _onApprove(self):
        """Handle approve button click."""
        self.hideApprovalButtons()
        self.actionApproved.emit()

    def _onCorrect(self):
        """Handle correct button click."""
        self.hideApprovalButtons()
        self.actionCorrectionRequested.emit()

    def showApprovalButtons(self, action_description=None):
        """Show the approval buttons after an action executes."""
        if action_description:
            self._approvalLabel.setText(f"Executed: {action_description[:50]}...")
        else:
            self._approvalLabel.setText("Action executed. Review in GUI:")
        self._approvalRow.show()
        self._inputField.setEnabled(False)

    def hideApprovalButtons(self):
        """Hide the approval buttons."""
        self._approvalRow.hide()
        self._inputField.setEnabled(True)

    def _onApiKeySubmit(self):
        """Handle API key submission."""
        key = self._apiKeyInput.text().strip()
        if key:
            self._apiKeyRow.hide()
            self._apiKeyInput.clear()
            self._inputField.setEnabled(True)
            self.apiKeySubmitted.emit(key)

    def showApiKeyPrompt(self):
        """Show the API key input row."""
        self._apiKeyRow.show()
        self._apiKeyInput.setFocus()
        self._inputField.setEnabled(False)
        self.setStatus("OpenAI API key required. Enter your key below.")

    def hideApiKeyPrompt(self):
        """Hide the API key input row."""
        self._apiKeyRow.hide()
        self._inputField.setEnabled(True)

    def mode(self):
        """Return the current mode."""
        return self._mode

    def backend(self):
        """Return the current backend."""
        return self._backend

    def setStatus(self, message):
        """Set the status message in the scrollable response area."""
        self._responseArea.setPlainText(message)
        # Auto-scroll to bottom
        scrollBar = self._responseArea.verticalScrollBar()
        scrollBar.setValue(scrollBar.maximum())

    def appendStatus(self, message):
        """Append a message to the response area."""
        self._responseArea.append(message)
        # Auto-scroll to bottom
        scrollBar = self._responseArea.verticalScrollBar()
        scrollBar.setValue(scrollBar.maximum())

    def clearStatus(self):
        """Clear the status message."""
        self._responseArea.clear()

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

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is in the title bar area
            titleBarRect = self._titleBar.geometry()
            containerPos = self._container.pos()
            # Adjust for container position within the main widget
            adjustedRect = titleBarRect.translated(containerPos)
            adjustedRect.translate(self.layout().contentsMargins().left(),
                                   self.layout().contentsMargins().top())
            if adjustedRect.contains(event.pos()):
                self._dragging = True
                self._dragPosition = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if self._dragging and self._dragPosition is not None:
            self.move(event.globalPosition().toPoint() - self._dragPosition)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._dragPosition = None
        super().mouseReleaseEvent(event)
