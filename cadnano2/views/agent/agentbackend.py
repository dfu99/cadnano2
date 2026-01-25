"""
agentbackend.py

Backend for agent processing with Ollama integration.
"""

import json
import urllib.request
import urllib.error

import cadnano2.util as util
util.qtWrapImport('QtCore', globals(), ['QObject', 'pyqtSignal', 'QThread'])


class OllamaWorker(QThread):
    """Worker thread for Ollama API calls."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, endpoint, model, prompt, system_prompt=None):
        super().__init__()
        self._endpoint = endpoint
        self._model = model
        self._prompt = prompt
        self._system_prompt = system_prompt

    def run(self):
        try:
            url = f"{self._endpoint}/api/generate"

            payload = {
                "model": self._model,
                "prompt": self._prompt,
                "stream": False
            }

            if self._system_prompt:
                payload["system"] = self._system_prompt

            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.finished.emit(result.get('response', ''))

        except urllib.error.URLError as e:
            self.error.emit(f"Connection error: {e.reason}")
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")


class AgentBackend(QObject):
    """
    Backend for processing agent commands with Ollama.

    Signals:
        responseReceived(str): Emitted when a response is ready
        errorOccurred(str): Emitted when an error occurs
        processingStarted(): Emitted when processing begins
        processingFinished(): Emitted when processing completes
        methodCallRequested(str, dict): Emitted when agent wants to call a method
    """

    responseReceived = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    processingStarted = pyqtSignal()
    processingFinished = pyqtSignal()
    methodCallRequested = pyqtSignal(str, dict)

    SYSTEM_PROMPT = """You are a cadnano DNA nanostructure design assistant. You help users modify DNA origami designs.

Available methods you can call:
- createScaffoldStrand(helix_num, start_idx, length): Create a scaffold strand on the specified helix

When the user asks to create or modify the design, respond with a JSON object containing:
{
    "method": "method_name",
    "params": {"param1": value1, "param2": value2}
}

If you need clarification, ask the user directly.
If the request doesn't require a method call, respond conversationally.

Examples:
- "Create a scaffold strand of length 100 on helix 0 starting at index 5"
  Response: {"method": "createScaffoldStrand", "params": {"helix_num": 0, "start_idx": 5, "length": 100}}

- "What methods are available?"
  Response: Available methods: createScaffoldStrand(helix_num, start_idx, length) - creates a scaffold strand on the specified helix.
"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._endpoint = "http://localhost:11434"
        self._model = "qwen2:1.5b"
        self._worker = None

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
        """
        self.processingStarted.emit()

        if mode == "developer":
            # In developer mode, try to parse as direct JSON method call
            # Format: {"method": "methodName", "params": {...}}
            # Or shorthand: methodName(param1=value1, param2=value2)
            self._handleDeveloperCommand(command)
            return

        # Create worker thread for Ollama call
        self._worker = OllamaWorker(
            self._endpoint,
            self._model,
            command,
            self.SYSTEM_PROMPT
        )
        self._worker.finished.connect(self._handleResponse)
        self._worker.error.connect(self._handleError)
        self._worker.start()

    def _handleResponse(self, response):
        """Handle response from Ollama."""
        # Try to parse as JSON method call
        try:
            # Look for JSON in the response
            response_stripped = response.strip()
            if response_stripped.startswith('{'):
                data = json.loads(response_stripped)
                if 'method' in data and 'params' in data:
                    # methodCallRequested handler will set the status
                    self.methodCallRequested.emit(data['method'], data['params'])
                    self.processingFinished.emit()
                    return
        except json.JSONDecodeError:
            pass

        # Regular text response
        self.responseReceived.emit(response)
        self.processingFinished.emit()

    def _handleError(self, error_msg):
        """Handle error from Ollama."""
        self.errorOccurred.emit(error_msg)
        self.responseReceived.emit(f"Error: {error_msg}")
        self.processingFinished.emit()

    def _handleDeveloperCommand(self, command):
        """
        Handle developer mode commands.

        Supports:
        - JSON format: {"method": "name", "params": {...}}
        - Shorthand: methodName(param1=value1, param2=value2)
        - Help: "help" or "?" to list available methods
        """
        command = command.strip()

        # Help command
        if command.lower() in ('help', '?'):
            help_text = """Available methods:
- createScaffoldStrand(helix_num, start_idx, length)
- createStapleStrand(helix_num, start_idx, length)
- getActivePartInfo()
- getPartInfo()

Examples:
  createScaffoldStrand(helix_num=0, start_idx=10, length=50)
  {"method": "createScaffoldStrand", "params": {"helix_num": 0, "start_idx": 10, "length": 50}}"""
            self.responseReceived.emit(help_text)
            self.processingFinished.emit()
            return

        # Try JSON format first
        if command.startswith('{'):
            try:
                data = json.loads(command)
                if 'method' in data and 'params' in data:
                    # methodCallRequested handler will set the status
                    self.methodCallRequested.emit(data['method'], data['params'])
                    self.processingFinished.emit()
                    return
            except json.JSONDecodeError as e:
                self.responseReceived.emit(f"JSON parse error: {e}")
                self.processingFinished.emit()
                return

        # Try shorthand format: methodName(param1=value1, ...)
        import re
        match = re.match(r'(\w+)\((.*)\)', command)
        if match:
            method_name = match.group(1)
            params_str = match.group(2).strip()

            params = {}
            if params_str:
                # Parse key=value pairs
                for param in params_str.split(','):
                    param = param.strip()
                    if '=' in param:
                        key, value = param.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Try to parse as number
                        try:
                            if '.' in value:
                                value = float(value)
                            else:
                                value = int(value)
                        except ValueError:
                            # Keep as string, remove quotes if present
                            if (value.startswith('"') and value.endswith('"')) or \
                               (value.startswith("'") and value.endswith("'")):
                                value = value[1:-1]
                        params[key] = value

            # methodCallRequested handler will set the status
            self.methodCallRequested.emit(method_name, params)
            self.processingFinished.emit()
            return

        # Unknown format
        self.responseReceived.emit(f"Unknown command format. Type 'help' for usage.")
        self.processingFinished.emit()

    def testConnection(self):
        """Test connection to Ollama server."""
        try:
            url = f"{self._endpoint}/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                models = [m['name'] for m in result.get('models', [])]
                return True, models
        except Exception as e:
            return False, str(e)
