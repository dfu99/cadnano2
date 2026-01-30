"""
agentbackend.py

Backend for agent processing with Ollama and OpenAI integration.
Supports multi-turn agentic conversations.
"""

import json
import os
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


class OpenAIWorker(QThread):
    """Worker thread for OpenAI API calls."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, api_key, model, messages):
        super().__init__()
        self._api_key = api_key
        self._model = model
        self._messages = messages

    def run(self):
        try:
            url = "https://api.openai.com/v1/chat/completions"

            payload = {
                "model": self._model,
                "messages": self._messages,
                "temperature": 1.0,
                "max_completion_tokens": 2048
            }

            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self._api_key}'
                }
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                choices = result.get('choices', [])
                if choices:
                    message = choices[0].get('message', {})
                    content = message.get('content', '')
                    self.finished.emit(content)
                else:
                    self.error.emit("No response choices returned from OpenAI")

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ''
            try:
                error_data = json.loads(body)
                error_msg = error_data.get('error', {}).get('message', body)
            except:
                error_msg = body
            self.error.emit(f"OpenAI API Error (HTTP {e.code}): {error_msg}")
        except urllib.error.URLError as e:
            self.error.emit(f"Connection error: {e.reason}")
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
    apiKeyNeeded = pyqtSignal()

    SYSTEM_PROMPT = """You are a cadnano DNA nanostructure design assistant. You modify DNA origami designs using primitive operations.

PRIMITIVE OPERATIONS:

QUERY (use these to understand the current state):
- listHelices(): List all helices with numbers, positions, parity
- listStrands(helix_num?, strand_type?): List all strands with endpoints and properties
- getStrandAt(helix_num, idx, strand_type): Get info about specific strand
- getSelectedStrands(): Get currently selected strands from GUI
- getPartSize(): Get valid index range

HELIX:
- createHelix(row, col): Create helix at grid position
- deleteHelix(helix_num): Remove a helix

STRAND (these are the core primitives):
- createScaffoldStrand(helix_num, start_idx, length): Create scaffold strand
- createStapleStrand(helix_num, start_idx, length): Create staple strand
- resizeStrand(helix_num, idx, strand_type, new_low, new_high): Change strand endpoints
- deleteStrand(helix_num, idx, strand_type): Remove a strand

CROSSOVER:
- createCrossover(helix1, idx1, helix2, idx2, strand_type): Connect strands
- removeCrossover(helix_num, idx, strand_type): Disconnect strands

SELECTION (for GUI-selected elements):
- moveSelection(delta): Move selected endpoints by delta bp
- clearSelection(): Clear selection

OTHER:
- extendPartSize(min_length_needed): Extend part to fit longer strands
- addInsertion(helix_num, idx, length): Add insertion/deletion

COMPOSING OPERATIONS:
Complex tasks are composed from primitives. Examples:

"Shorten all scaffold strands by 2 bp":
1. listStrands(strand_type="scaffold") → get all scaffold strands
2. For each strand, based on parity:
   - even parity: 5'→3' goes right, so shorten from high end: resizeStrand(..., new_high=high-2)
   - odd parity: 5'→3' goes left, so shorten from low end: resizeStrand(..., new_low=low+2)

"Move selected strand 3 bp right":
1. moveSelection(delta=3)

PARITY RULES:
- even parity (row%2 == col%2): scaffold 5'→3' goes LEFT to RIGHT (increasing idx)
- odd parity (row%2 != col%2): scaffold 5'→3' goes RIGHT to LEFT (decreasing idx)

RESPONSE FORMAT:
- To call a method: {"method": "methodName", "params": {"param1": value1}}
- When done: {"done": true, "message": "Summary"}

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

Step 1: Extend part size to fit 84bp strands (default is only 42bp)
{"method": "extendPartSize", "params": {"min_length_needed": 84}}

Step 2: Get positions
{"method": "getHoneycombPositions", "params": {"num_helices": 6}}

Step 3-8: Create 6 helices
{"method": "createHelix", "params": {"row": 20, "col": 20}}
{"method": "createHelix", "params": {"row": 20, "col": 21}}
{"method": "createHelix", "params": {"row": 21, "col": 20}}
{"method": "createHelix", "params": {"row": 21, "col": 21}}
{"method": "createHelix", "params": {"row": 22, "col": 20}}
{"method": "createHelix", "params": {"row": 22, "col": 21}}

Step 9-14: Create scaffold strands (84bp each)
{"method": "createScaffoldStrand", "params": {"helix_num": 0, "start_idx": 0, "length": 84}}
... repeat for helices 1-5

Step 15: Get valid crossover positions
{"method": "getValidCrossoverPositions", "params": {"helix1": 0, "helix2": 1, "strand_type": "scaffold"}}

Step 16+: Create crossovers between adjacent helices
{"method": "createCrossover", "params": {"helix1": 0, "idx1": 11, "helix2": 1, "idx2": 11, "strand_type": "scaffold"}}

Step N: Verify the result
{"method": "verify6HelixBundle", "params": {}}

Final: {"done": true, "message": "Created 6-helix bundle with 6 helices, scaffold strands, and crossovers. Score: X.XX"}
"""

    MAX_ITERATIONS = 50  # Safety limit for agent loop

    # Available backend types
    BACKEND_OLLAMA = "ollama"
    BACKEND_OPENAI = "openai"

    def __init__(self, parent=None):
        super().__init__(parent)
        # Backend configuration
        self._backendType = self.BACKEND_OLLAMA  # Default to Ollama

        # Ollama settings
        self._endpoint = "http://localhost:11434"
        self._ollamaModel = "qwen3:1.7b"

        # OpenAI settings
        self._openaiApiKey = self._loadApiKey()
        self._openaiModel = "gpt-5"  # Default to GPT-5

        self._worker = None
        self._conversation = []  # Multi-turn conversation history
        self._isAgentLoop = False  # Whether we're in an agent loop
        self._iterationCount = 0  # Track iterations for safety

    @property
    def backendType(self):
        return self._backendType

    @backendType.setter
    def backendType(self, value):
        if value in (self.BACKEND_OLLAMA, self.BACKEND_OPENAI):
            self._backendType = value
        else:
            raise ValueError(f"Unknown backend type: {value}")

    @property
    def endpoint(self):
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value):
        self._endpoint = value

    @property
    def model(self):
        """Return the current model based on backend type."""
        if self._backendType == self.BACKEND_OPENAI:
            return self._openaiModel
        return self._ollamaModel

    @model.setter
    def model(self, value):
        """Set the model for the current backend type."""
        if self._backendType == self.BACKEND_OPENAI:
            self._openaiModel = value
        else:
            self._ollamaModel = value

    @property
    def openaiApiKey(self):
        return self._openaiApiKey

    @openaiApiKey.setter
    def openaiApiKey(self, value):
        self._openaiApiKey = value

    def setBackend(self, backend_type, model=None, api_key=None):
        """
        Configure the backend.

        Args:
            backend_type (str): 'ollama' or 'openai'
            model (str): Model name (optional)
            api_key (str): API key for OpenAI (optional, can also use OPENAI_API_KEY env var)
        """
        self.backendType = backend_type
        if model:
            self.model = model
        if api_key:
            self._openaiApiKey = api_key
        print(f"[Agent] Backend set to: {backend_type}, model: {self.model}")

    @staticmethod
    def _envFilePath():
        """Return path to the .env.cadnano file."""
        config_dir = os.path.expanduser("~/.cadnano2")
        return os.path.join(config_dir, ".env.cadnano")

    @staticmethod
    def _loadApiKey():
        """Load the OpenAI API key from .env.cadnano or environment."""
        # First check environment variable
        key = os.environ.get('OPENAI_API_KEY', '')
        if key:
            return key
        # Then check .env.cadnano file
        env_path = AgentBackend._envFilePath()
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('OPENAI_API_KEY=') and not line.startswith('#'):
                            return line.split('=', 1)[1].strip()
            except OSError:
                pass
        return ''

    @staticmethod
    def saveApiKey(api_key):
        """Save the OpenAI API key to ~/.cadnano2/.env.cadnano."""
        config_dir = os.path.expanduser("~/.cadnano2")
        os.makedirs(config_dir, exist_ok=True)
        env_path = AgentBackend._envFilePath()

        # Read existing lines (if any), replacing any existing key
        lines = []
        found = False
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('OPENAI_API_KEY='):
                            lines.append(f'OPENAI_API_KEY={api_key}\n')
                            found = True
                        else:
                            lines.append(line)
            except OSError:
                pass
        if not found:
            lines.append(f'OPENAI_API_KEY={api_key}\n')

        with open(env_path, 'w') as f:
            f.writelines(lines)
        print(f"[Agent] API key saved to {env_path}")

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
        self._iterationCount = 0
        self._continueAgentLoop()

    def _continueAgentLoop(self):
        """Continue the agent loop with the current conversation."""
        self._iterationCount += 1

        # Safety check for maximum iterations
        if self._iterationCount > self.MAX_ITERATIONS:
            self._isAgentLoop = False
            self.responseReceived.emit(f"Agent stopped: exceeded maximum iterations ({self.MAX_ITERATIONS})")
            self.processingFinished.emit()
            return

        # Create appropriate worker based on backend type
        if self._backendType == self.BACKEND_OPENAI:
            if not self._openaiApiKey:
                self._isAgentLoop = False
                self.apiKeyNeeded.emit()
                self.processingFinished.emit()
                return
            self._worker = OpenAIWorker(
                self._openaiApiKey,
                self._openaiModel,
                self._conversation
            )
        else:
            self._worker = OllamaWorker(
                self._endpoint,
                self._ollamaModel,
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

        # Add the result as feedback
        self._conversation.append({
            "role": "user",
            "content": f"Result: {result}"
        })
        self._continueAgentLoop()

    def _extractFirstJsonObject(self, text):
        """
        Extract the first valid JSON object from text.
        Handles cases where multiple JSON objects are present,
        JSON in markdown code blocks, etc.

        Returns:
            dict or None: Parsed JSON object, or None if not found
        """
        import re

        # Try multiple patterns for markdown code blocks
        code_block_patterns = [
            r'```json\s*(\{.*?\})\s*```',  # ```json {...} ```
            r'```\s*(\{.*?\})\s*```',       # ``` {...} ```
            r'`(\{[^`]+\})`',               # `{...}`
        ]
        for pattern in code_block_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        # Fall back to brace matching - find JSON objects with "method" or "done" keys
        depth = 0
        start = None

        for i, char in enumerate(text):
            if char == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    json_str = text[start:i + 1]
                    try:
                        obj = json.loads(json_str)
                        # Only return if it looks like a valid action
                        if isinstance(obj, dict) and ('method' in obj or 'done' in obj):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    # Reset and try next object
                    start = None
                    continue
        return None

    def _handleAgentResponse(self, response):
        """Handle response from Ollama in agent loop."""
        print(f"[Agent] Raw response length: {len(response)}")
        print(f"[Agent] Raw response preview: {response[:300]}...")

        # Add assistant response to conversation
        self._conversation.append({
            "role": "assistant",
            "content": response
        })

        # Try to parse as JSON
        response_stripped = response.strip()

        # Handle /think tags from qwen3 - extract content after </think>
        thinking_content = None
        if '/think>' in response_stripped:
            # Find the thinking part and the actual response
            think_end = response_stripped.rfind('</think>')
            if think_end != -1:
                thinking_content = response_stripped[:think_end]
                response_stripped = response_stripped[think_end + 8:].strip()
                # Emit thinking for display (optional)
                self.agentThinking.emit(thinking_content)

        # Try to find JSON - first in the main response, then in thinking content
        data = self._extractFirstJsonObject(response_stripped)

        # If no valid JSON in response, check thinking content
        if data is None and thinking_content:
            data = self._extractFirstJsonObject(thinking_content)

        if data is not None:
            print(f"[Agent] Parsed JSON: {data}")

            # Check if agent is done
            if data.get('done'):
                self._isAgentLoop = False
                self.responseReceived.emit(f"Done: {data.get('message', 'Task complete')}")
                self.processingFinished.emit()
                return

            # Check if it's a method call
            if 'method' in data:
                params = data.get('params', {})
                print(f"[Agent] Emitting methodCallRequested: {data['method']}")
                # Show the user what method is being called
                self.responseReceived.emit(f"Calling: {data['method']}({params})")
                self.methodCallRequested.emit(data['method'], params)
                # Don't emit processingFinished - wait for feedback
                return
        else:
            print(f"[Agent] No valid JSON found in response")
            print(f"[Agent] Response stripped: {response_stripped[:200]}...")
            if thinking_content:
                print(f"[Agent] Thinking content: {thinking_content[:200]}...")

        # Plain text response (explanation or question)
        # Check if it looks like the agent is asking a question that needs user input
        response_lower = response_stripped.lower() if response_stripped else response.lower()

        # More specific patterns that indicate the agent needs user clarification
        needs_user_input = any(phrase in response_lower for phrase in [
            'would you like me to',
            'do you want me to',
            'should i proceed',
            'please confirm',
            'which option',
            'what would you prefer',
            'let me know if',
            'please specify',
            'could you clarify',
            'what should i',
            'how would you like'
        ])

        if needs_user_input:
            # Agent is asking a question - stop and wait for user
            self._isAgentLoop = False
            self.responseReceived.emit(response_stripped if response_stripped else response)
            self.processingFinished.emit()
        else:
            # Agent is explaining/thinking - prompt it to provide a JSON action
            self.responseReceived.emit(response_stripped if response_stripped else response)
            self._conversation.append({
                "role": "user",
                "content": "Please respond with ONLY a JSON object. Either a method call like {\"method\": \"methodName\", \"params\": {...}} or {\"done\": true, \"message\": \"...\"}. No explanation, just the JSON."
            })
            self._continueAgentLoop()

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
        """Test connection to the configured backend."""
        if self._backendType == self.BACKEND_OPENAI:
            return self._testOpenAIConnection()
        else:
            return self._testOllamaConnection()

    def _testOllamaConnection(self):
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

    def _testOpenAIConnection(self):
        """Test connection to OpenAI API."""
        if not self._openaiApiKey:
            return False, "OpenAI API key not set"
        try:
            url = "https://api.openai.com/v1/models"
            req = urllib.request.Request(
                url,
                headers={'Authorization': f'Bearer {self._openaiApiKey}'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                # Filter to show only chat models
                models = [m['id'] for m in result.get('data', [])
                         if 'gpt' in m['id']]
                return True, models[:10]  # Limit to first 10
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Invalid API key"
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, str(e)
