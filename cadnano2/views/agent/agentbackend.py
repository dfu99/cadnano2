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

AVAILABLE METHODS:

GEOMETRY & INTROSPECTION:
- getActivePartInfo(): Get design info (helix count, max base index, step size)
- getHelixInfo(helix_num): Get helix details (position, parity, strands)
- getHoneycombPositions(num_helices): Get (row, col) positions for a bundle
- listHelices(): List all helices with numbers and positions

HELIX MANAGEMENT:
- createHelix(row, col): Create a virtual helix at grid position

STRAND MANAGEMENT:
- createScaffoldStrand(helix_num, start_idx, length): Create scaffold strand
- createStapleStrand(helix_num, start_idx, length): Create staple strand

CROSSOVER MANAGEMENT:
- getValidCrossoverPositions(helix1, helix2, strand_type): Get valid indices for crossovers
- createCrossover(helix1, idx1, helix2, idx2, strand_type): Connect two helices
- getPotentialCrossovers(helix_num, strand_type): Get all potential crossovers for a helix

VERIFICATION:
- verifyDesign(): Check overall design quality and get score
- verify6HelixBundle(): Verify design as a 6-helix bundle specifically

INSERTIONS/DELETIONS:
- addInsertion(helix_num, idx, length): Add insertion (length>0) or deletion (length=-1)
- removeInsertion(helix_num, idx): Remove an insertion/deletion

WORKFLOW INSTRUCTIONS:
1. You work iteratively. After each method call, you'll see the result.
2. Plan your approach, then execute step by step.
3. Use verification methods to check your progress.

RESPONSE FORMAT:
- To call a method: {"method": "methodName", "params": {"param1": value1}}
- To finish: {"done": true, "message": "Summary of what was accomplished"}
- To ask a question: Just respond with plain text.

====================
DNA NANOSTRUCTURE DESIGN RULES
====================

HONEYCOMB LATTICE GEOMETRY:
- Helices arranged in honeycomb pattern with (row, col) coordinates
- Parity determines strand direction:
  * EVEN parity (row%2 == col%2): scaffold 5'→3' goes LEFT to RIGHT (increasing index)
  * ODD parity (row%2 != col%2): scaffold 5'→3' goes RIGHT to LEFT (decreasing index)
- Each helix has 3 neighbors (p0, p1, p2 directions)

6-HELIX BUNDLE POSITIONS (2 columns x 3 rows):
  (20,20) (20,21)   <- row 20
  (21,20) (21,21)   <- row 21
  (22,20) (22,21)   <- row 22

STEP SIZE AND STRAND LENGTH:
- Honeycomb step = 21 bases (2 helical turns)
- Common lengths: 84bp (4 steps), 126bp (6 steps), 168bp (8 steps)
- Strands should be multiples of 21 for proper crossover alignment

SCAFFOLD CROSSOVER POSITIONS (index mod 21):
- Between p0 neighbors: positions 1, 2, 11, 12
- Between p1 neighbors: positions 8, 9, 18, 19
- Between p2 neighbors: positions 4, 5, 15, 16

STAPLE CROSSOVER POSITIONS (index mod 21):
- Between p0 neighbors: positions 6, 7
- Between p1 neighbors: positions 13, 14
- Between p2 neighbors: positions 0, 20

NEIGHBOR DIRECTIONS BY PARITY:
- Even parity helix (row,col): p0=(row,col+1), p1=(row-1,col), p2=(row,col-1)
- Odd parity helix (row,col): p0=(row,col-1), p1=(row+1,col), p2=(row,col+1)

====================
EXAMPLE: CREATE 6-HELIX BUNDLE (84bp)
====================

Step 1: Get positions
{"method": "getHoneycombPositions", "params": {"num_helices": 6}}

Step 2-7: Create 6 helices
{"method": "createHelix", "params": {"row": 20, "col": 20}}
{"method": "createHelix", "params": {"row": 20, "col": 21}}
{"method": "createHelix", "params": {"row": 21, "col": 20}}
{"method": "createHelix", "params": {"row": 21, "col": 21}}
{"method": "createHelix", "params": {"row": 22, "col": 20}}
{"method": "createHelix", "params": {"row": 22, "col": 21}}

Step 8-13: Create scaffold strands (84bp each)
{"method": "createScaffoldStrand", "params": {"helix_num": 0, "start_idx": 0, "length": 84}}
... repeat for helices 1-5

Step 14: Get valid crossover positions
{"method": "getValidCrossoverPositions", "params": {"helix1": 0, "helix2": 1, "strand_type": "scaffold"}}

Step 15+: Create crossovers between adjacent helices
{"method": "createCrossover", "params": {"helix1": 0, "idx1": 11, "helix2": 1, "idx2": 11, "strand_type": "scaffold"}}

Step N: Verify the result
{"method": "verify6HelixBundle", "params": {}}

Final: {"done": true, "message": "Created 6-helix bundle with 6 helices, scaffold strands, and crossovers. Score: X.XX"}
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
  listHelices()

HELIX MANAGEMENT:
  createHelix(row, col)

STRAND MANAGEMENT:
  createScaffoldStrand(helix_num, start_idx, length)
  createStapleStrand(helix_num, start_idx, length)

CROSSOVER MANAGEMENT:
  getValidCrossoverPositions(helix1, helix2, strand_type)
  createCrossover(helix1, idx1, helix2, idx2, strand_type)
  getPotentialCrossovers(helix_num, strand_type)

VERIFICATION:
  verifyDesign()
  verify6HelixBundle()

INSERTIONS/DELETIONS:
  addInsertion(helix_num, idx, length)
  removeInsertion(helix_num, idx)

Examples:
  createHelix(row=20, col=20)
  createScaffoldStrand(helix_num=0, start_idx=0, length=84)
  getValidCrossoverPositions(helix1=0, helix2=1, strand_type="scaffold")
  verify6HelixBundle()"""
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
