"""
agentbackend.py

Backend for agent processing with Ollama integration.
Supports multi-turn agentic conversations.
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

    def __init__(self, endpoint, model, messages):
        super().__init__()
        self._endpoint = endpoint
        self._model = model
        self._messages = messages

    def run(self):
        try:
            url = f"{self._endpoint}/api/chat"

            payload = {
                "model": self._model,
                "messages": self._messages,
                "stream": False
            }

            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                message = result.get('message', {})
                self.finished.emit(message.get('content', ''))

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ''
            self.error.emit(f"HTTP {e.code}: {e.reason}. {body}")
        except urllib.error.URLError as e:
            self.error.emit(f"Connection error: {e.reason}. Is Ollama running?")
        except Exception as e:
            self.error.emit(f"Error: {type(e).__name__}: {str(e)}")


class AgentBackend(QObject):
    """
    Backend for processing agent commands with Ollama.
    Supports multi-turn agentic conversations.

    Signals:
        responseReceived(str): Emitted when a response is ready
        errorOccurred(str): Emitted when an error occurs
        processingStarted(): Emitted when processing begins
        processingFinished(): Emitted when processing completes
        methodCallRequested(str, dict): Emitted when agent wants to call a method
        agentThinking(str): Emitted when agent is reasoning (for display)
    """

    responseReceived = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    processingStarted = pyqtSignal()
    processingFinished = pyqtSignal()
    methodCallRequested = pyqtSignal(str, dict)
    agentThinking = pyqtSignal(str)

    SYSTEM_PROMPT = """You are a cadnano DNA nanostructure design assistant. You help users create and modify DNA origami designs through iterative method calls.

Available methods:

GEOMETRY & INTROSPECTION:
- getActivePartInfo(): Get info about the current design (helix count, max base index)
- getHelixInfo(helix_num): Get detailed info about a specific helix
- getHoneycombPositions(num_helices): Get (row, col) positions for a honeycomb bundle
- getPotentialCrossovers(helix_num, strand_type): Get crossover positions ("scaffold" or "staple")

HELIX MANAGEMENT:
- createHelix(row, col): Create a virtual helix at grid position
- listHelices(): List all helices with their numbers and positions

STRAND MANAGEMENT:
- createScaffoldStrand(helix_num, start_idx, length): Create scaffold strand
- createStapleStrand(helix_num, start_idx, length): Create staple strand

CROSSOVER MANAGEMENT:
- createCrossover(helix1, idx1, helix2, idx2, strand_type): Connect two helices
- findCrossoversWithSpacing(strand_type, min_spacing): Find crossovers with minimum bp spacing

INSERTIONS/DELETIONS:
- addInsertion(helix_num, idx, length): Add insertion (length>0) or deletion (length=-1)
- removeInsertion(helix_num, idx): Remove an insertion/deletion

WORKFLOW:
You work iteratively. After each method call, you'll see the result and decide the next step.

To call a method, respond with ONLY a JSON object:
{"method": "methodName", "params": {"param1": value1}}

To finish the task, respond with:
{"done": true, "message": "Summary of what was accomplished"}

To ask a clarifying question, just respond with plain text.

HONEYCOMB LATTICE GEOMETRY:
- For a 6-helix bundle, use positions like: (20,20), (20,21), (21,20), (21,21), (22,20), (22,21)
- Even parity: row%2 == col%2, scaffold goes left-to-right (5'→3')
- Odd parity: row%2 != col%2, scaffold goes right-to-left (5'→3')
- Step size is 21 bases
- Scaffold crossovers align at specific positions within each 21-base step
- Staple crossovers are at different positions than scaffold

CROSSOVER POSITIONS (per 21-base step, modulo 21):
Scaffold crossovers between neighbors depend on neighbor direction (p0, p1, p2).
Staple crossovers are at positions 0, 6, 7, 13, 14, 20 (varies by neighbor).

Example workflow for "Create a 6-helix bundle":
1. getHoneycombPositions(6) → get positions
2. createHelix(row, col) for each position
3. createScaffoldStrand on each helix (full length)
4. createStapleStrand on each helix (full length)
5. getPotentialCrossovers to find crossover positions
6. createCrossover to connect helices
7. {"done": true, "message": "Created 6-helix bundle with crossovers"}
"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._endpoint = "http://localhost:11434"
        self._model = "qwen3:4b"
        self._worker = None
        self._conversation = []  # Multi-turn conversation history
        self._isAgentLoop = False  # Whether we're in an agent loop

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
            self._handleDeveloperCommand(command)
            return

        # Start new conversation with user command
        self._conversation = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": command}
        ]
        self._isAgentLoop = True
        self._continueAgentLoop()

    def _continueAgentLoop(self):
        """Continue the agent loop with the current conversation."""
        self._worker = OllamaWorker(
            self._endpoint,
            self._model,
            self._conversation
        )
        self._worker.finished.connect(self._handleAgentResponse)
        self._worker.error.connect(self._handleError)
        self._worker.start()

    def feedbackToAgent(self, result):
        """
        Feed the result of a method call back to the agent.

        Args:
            result (str): The result message from method execution
        """
        if not self._isAgentLoop:
            return

        # Add the result as an assistant message observation
        self._conversation.append({
            "role": "user",
            "content": f"Result: {result}\n\nWhat's the next step?"
        })
        self._continueAgentLoop()

    def _handleAgentResponse(self, response):
        """Handle response from Ollama in agent loop."""
        # Add assistant response to conversation
        self._conversation.append({
            "role": "assistant",
            "content": response
        })

        # Try to parse as JSON
        response_stripped = response.strip()

        # Handle /think tags from qwen3 - extract content after </think>
        if '/think>' in response_stripped:
            # Find the thinking part and the actual response
            think_end = response_stripped.rfind('</think>')
            if think_end != -1:
                thinking = response_stripped[:think_end]
                response_stripped = response_stripped[think_end + 8:].strip()
                # Emit thinking for display (optional)
                self.agentThinking.emit(thinking)

        # Try to find JSON in response
        json_start = response_stripped.find('{')
        json_end = response_stripped.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            try:
                json_str = response_stripped[json_start:json_end]
                data = json.loads(json_str)

                # Check if agent is done
                if data.get('done'):
                    self._isAgentLoop = False
                    self.responseReceived.emit(f"Done: {data.get('message', 'Task complete')}")
                    self.processingFinished.emit()
                    return

                # Check if it's a method call
                if 'method' in data:
                    params = data.get('params', {})
                    self.methodCallRequested.emit(data['method'], params)
                    # Don't emit processingFinished - wait for feedback
                    return

            except json.JSONDecodeError:
                pass

        # Plain text response (question or explanation)
        self._isAgentLoop = False
        self.responseReceived.emit(response_stripped if response_stripped else response)
        self.processingFinished.emit()

    def _handleError(self, error_msg):
        """Handle error from Ollama."""
        self._isAgentLoop = False
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

GEOMETRY & INTROSPECTION:
  getActivePartInfo()
  getHelixInfo(helix_num)
  getHoneycombPositions(num_helices)
  getPotentialCrossovers(helix_num, strand_type)

HELIX MANAGEMENT:
  createHelix(row, col)
  listHelices()

STRAND MANAGEMENT:
  createScaffoldStrand(helix_num, start_idx, length)
  createStapleStrand(helix_num, start_idx, length)

CROSSOVER MANAGEMENT:
  createCrossover(helix1, idx1, helix2, idx2, strand_type)

INSERTIONS/DELETIONS:
  addInsertion(helix_num, idx, length)
  removeInsertion(helix_num, idx)

Examples:
  createHelix(row=20, col=20)
  createScaffoldStrand(helix_num=0, start_idx=0, length=84)
  {"method": "createHelix", "params": {"row": 20, "col": 20}}"""
            self.responseReceived.emit(help_text)
            self.processingFinished.emit()
            return

        # Try JSON format first
        if command.startswith('{'):
            try:
                data = json.loads(command)
                if 'method' in data:
                    params = data.get('params', {})
                    self.methodCallRequested.emit(data['method'], params)
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

            self.methodCallRequested.emit(method_name, params)
            self.processingFinished.emit()
            return

        # Unknown format
        self.responseReceived.emit("Unknown command format. Type 'help' for usage.")
        self.processingFinished.emit()

    def stopAgentLoop(self):
        """Stop the current agent loop."""
        self._isAgentLoop = False
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
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
