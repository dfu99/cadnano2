"""
agentbackend.py

Placeholder backend for agent processing.
Future integration point for Ollama/Qwen-4B or similar local models.
"""

import cadnano2.util as util
util.qtWrapImport('QtCore', globals(), ['QObject', 'pyqtSignal'])


class AgentBackend(QObject):
    """
    Backend for processing agent commands.

    Signals:
        responseReceived(str): Emitted when a response is ready
        errorOccurred(str): Emitted when an error occurs
        processingStarted(): Emitted when processing begins
        processingFinished(): Emitted when processing completes
    """

    responseReceived = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    processingStarted = pyqtSignal()
    processingFinished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._endpoint = "http://localhost:11434"  # Default Ollama endpoint
        self._model = "qwen2:4b"  # Default model

    @property
    def endpoint(self):
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value):
        self._endpoint = value

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value

    def processCommand(self, command, mode="edit"):
        """
        Process a command from the agent dialog.

        Args:
            command (str): The user's command/query
            mode (str): Either "edit" or "developer"

        This is a placeholder that will be replaced with actual
        Ollama integration in the future.
        """
        self.processingStarted.emit()

        # Placeholder response - to be replaced with actual model call
        if mode == "edit":
            response = f"[Edit Mode] Received command: '{command}'. Agent backend not yet connected."
        else:
            response = f"[Developer Mode] Received command: '{command}'. Agent backend not yet connected."

        self.responseReceived.emit(response)
        self.processingFinished.emit()
