"""
agentbackend.py

Backend for agent processing with Ollama, OpenAI, and Claude (Anthropic) integration.
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


class ClaudeWorker(QThread):
    """Worker thread for Anthropic Claude API calls with native tool use."""

    finished = pyqtSignal(object)   # Emits full response dict
    error = pyqtSignal(str)

    def __init__(self, api_key, model, messages, tools, system_prompt):
        super().__init__()
        self._api_key = api_key
        self._model = model
        self._messages = messages
        self._tools = tools
        self._system_prompt = system_prompt

    def run(self):
        try:
            url = "https://api.anthropic.com/v1/messages"

            payload = {
                "model": self._model,
                "max_tokens": 8192,
                "system": self._system_prompt,
                "tools": self._tools,
                "messages": self._messages
            }

            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': self._api_key,
                    'anthropic-version': '2023-06-01'
                }
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.finished.emit(result)

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ''
            try:
                error_data = json.loads(body)
                error_msg = error_data.get('error', {}).get('message', body)
            except Exception:
                error_msg = body
            self.error.emit(f"Claude API Error (HTTP {e.code}): {error_msg}")
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

    SYSTEM_PROMPT = """You are a cadnano DNA nanostructure design assistant.

AVAILABLE TOOLS:

UNDERSTAND THE DESIGN (call these first):
- analyzeDesign(): Complete state dump — all helices, strands, crossovers, issues
- describeHelix(helix_num): Everything about one helix — parity, neighbors, strands, valid crossover positions
- suggestCrossovers(helix1, helix2, strand_type, min_spacing?): Valid crossover positions with recommendations
- getNeighborPairs(): All neighbor pairs with direction info

BUILD (batch operations — preferred for multi-step tasks):
- createHelicesWithStrands(num_helices, strand_type, length): Create multiple helices with strands in one step. Pass num_helices (e.g. 6) for a standard bundle — positions are computed automatically. Standard sizes: 2, 6, 7, 19. strand_type can be "scaffold", "staple", or "both". Auto-extends part size. You may also pass an explicit positions list of [row, col] pairs instead of num_helices.
- addCrossoversForPair(helix1, helix2, strand_type, positions?, spacing?): Add crossovers between two helices. Auto-computes positions if not specified.
- addAllNeighborCrossovers(strand_type, spacing?): Wire up all neighbor pairs with crossovers
- resizeAllStrands(strand_type, new_length?, delta?, helix_num?): Resize strands in bulk. Respects parity for which end to resize.

FINE-GRAINED CONTROL (when batch tools aren't enough):
- createHelix(row, col), deleteHelix(helix_num)
- createScaffoldStrand(helix_num, start_idx, length), createStapleStrand(helix_num, start_idx, length)
- resizeStrand(helix_num, idx, strand_type, new_low, new_high), deleteStrand(helix_num, idx, strand_type)
- createCrossover(helix1, idx1, helix2, idx2, strand_type): Double crossover — paired index found automatically
- createHalfCrossover(helix1, idx1, helix2, idx2, strand_type): Single half-crossover (rare)
- removeCrossover(helix_num, idx, strand_type)
- moveCrossover(helix1, helix2, idx, strand_type, delta): Move crossover freely by delta bp
- extendPartSize(min_length_needed)

SELECTION (for GUI-selected elements):
- selectStrand(helix_num, idx, strand_type), selectEndpoint(helix_num, idx, strand_type, which_end)
- selectCrossover(helix1, helix2, idx, strand_type)
- moveSelection(delta): Move/resize selected elements
- clearSelection(), getSelectedStrands()

QUERY:
- listHelices(), listStrands(helix_num?, strand_type?), listCrossovers(helix_num?, strand_type?)
- getStrandAt(helix_num, idx, strand_type), getPartSize()
- getHoneycombPositions(num_helices)

VERIFICATION:
- verifyDesign(), verify6HelixBundle()

HONEYCOMB STEP SIZE: 21bp. Common lengths: 84bp (4 steps), 126bp (6 steps).

EXAMPLE — Create a 6-helix bundle with 84bp scaffold:
1. {"method": "createHelicesWithStrands", "params": {"num_helices": 6, "strand_type": "scaffold", "length": 84}}
2. {"method": "addAllNeighborCrossovers", "params": {"strand_type": "scaffold"}}
3. {"method": "verifyDesign", "params": {}}
4. {"done": true, "message": "Created 6-helix bundle with scaffold strands and crossovers."}

RESPONSE FORMAT:
- To call a method: {"method": "methodName", "params": {"param1": value1}}
- When done: {"done": true, "message": "Summary"}
"""

    CLAUDE_SYSTEM_PROMPT = """You are a cadnano DNA nanostructure design assistant.
Use the provided tools to inspect and modify the design.
Always call analyzeDesign first if you don't know the current state.
Honeycomb lattice step size is 21bp. Common lengths: 84bp (4×21), 126bp (6×21).
For standard bundles, use createHelicesWithStrands with num_helices (e.g. num_helices=6) — never invent lattice coordinates yourself.
When done, call the done tool with a summary of what was accomplished."""

    MAX_ITERATIONS = 50  # Safety limit for agent loop

    # Available backend types
    BACKEND_OLLAMA = "ollama"
    BACKEND_OPENAI = "openai"
    BACKEND_CLAUDE = "claude"

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

        # Claude settings
        self._claudeApiKey = self._loadAnthropicApiKey()
        self._claudeModel = "claude-opus-4-6"

        # Claude conversation state
        self._claudeConversation = []   # Claude-format messages
        self._pendingToolUses = []      # Queue of {id, name, input} blocks
        self._toolResultsForTurn = []   # Accumulated tool_results for current turn

        self._worker = None
        self._conversation = []  # Multi-turn conversation history (Ollama/OpenAI)
        self._isAgentLoop = False  # Whether we're in an agent loop
        self._iterationCount = 0  # Track iterations for safety

    @property
    def backendType(self):
        return self._backendType

    @backendType.setter
    def backendType(self, value):
        if value in (self.BACKEND_OLLAMA, self.BACKEND_OPENAI, self.BACKEND_CLAUDE):
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
        if self._backendType == self.BACKEND_CLAUDE:
            return self._claudeModel
        return self._ollamaModel

    @model.setter
    def model(self, value):
        """Set the model for the current backend type."""
        if self._backendType == self.BACKEND_OPENAI:
            self._openaiModel = value
        elif self._backendType == self.BACKEND_CLAUDE:
            self._claudeModel = value
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
            backend_type (str): 'ollama', 'openai', or 'claude'
            model (str): Model name (optional)
            api_key (str): API key for OpenAI or Claude (optional)
        """
        self.backendType = backend_type
        if model:
            self.model = model
        if api_key:
            if backend_type == self.BACKEND_CLAUDE:
                self._claudeApiKey = api_key
            else:
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

    @staticmethod
    def _loadAnthropicApiKey():
        """Load the Anthropic API key from ANTHROPIC_API_KEY env var or .env.cadnano."""
        key = os.environ.get('ANTHROPIC_API_KEY', '')
        if key:
            return key
        env_path = AgentBackend._envFilePath()
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('ANTHROPIC_API_KEY=') and not line.startswith('#'):
                            return line.split('=', 1)[1].strip()
            except OSError:
                pass
        return ''

    @staticmethod
    def saveAnthropicApiKey(api_key):
        """Save the Anthropic API key to ~/.cadnano2/.env.cadnano."""
        config_dir = os.path.expanduser("~/.cadnano2")
        os.makedirs(config_dir, exist_ok=True)
        env_path = AgentBackend._envFilePath()

        lines = []
        found = False
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('ANTHROPIC_API_KEY='):
                            lines.append(f'ANTHROPIC_API_KEY={api_key}\n')
                            found = True
                        else:
                            lines.append(line)
            except OSError:
                pass
        if not found:
            lines.append(f'ANTHROPIC_API_KEY={api_key}\n')

        with open(env_path, 'w') as f:
            f.writelines(lines)
        print(f"[Agent] Anthropic API key saved to {env_path}")

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

        self._isAgentLoop = True
        self._iterationCount = 0

        if self._backendType == self.BACKEND_CLAUDE:
            # Claude uses native tool use — no system prompt in messages
            self._claudeConversation = [{"role": "user", "content": command}]
            self._pendingToolUses = []
            self._toolResultsForTurn = []
        else:
            # Ollama/OpenAI: system prompt in messages list
            self._conversation = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": command}
            ]

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
        if self._backendType == self.BACKEND_CLAUDE:
            if not self._claudeApiKey:
                self._isAgentLoop = False
                self.apiKeyNeeded.emit()
                self.processingFinished.emit()
                return
            from .agenttools import TOOL_SCHEMAS
            self._worker = ClaudeWorker(
                self._claudeApiKey,
                self._claudeModel,
                self._claudeConversation,
                TOOL_SCHEMAS,
                self.CLAUDE_SYSTEM_PROMPT
            )
            self._worker.finished.connect(self._handleClaudeResponse)
            self._worker.error.connect(self._handleError)
        elif self._backendType == self.BACKEND_OPENAI:
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
            self._worker.finished.connect(self._handleAgentResponse)
            self._worker.error.connect(self._handleError)
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

        if self._backendType == self.BACKEND_CLAUDE:
            # Pop the tool that just completed and accumulate its result
            if self._pendingToolUses:
                tool = self._pendingToolUses.pop(0)
                self._toolResultsForTurn.append({
                    'type': 'tool_result',
                    'tool_use_id': tool['id'],
                    'content': str(result)
                })
            self._processNextPendingTool()
        else:
            # Ollama/OpenAI: add result as a user message
            self._conversation.append({
                "role": "user",
                "content": f"Result: {result}"
            })
            self._continueAgentLoop()

    def _handleClaudeResponse(self, response):
        """Handle a native tool-use response from the Claude API."""
        stop_reason = response.get('stop_reason')
        content = response.get('content', [])  # list of content blocks

        print(f"[Claude] stop_reason={stop_reason}, content blocks={len(content)}")

        # Append assistant turn to conversation
        self._claudeConversation.append({'role': 'assistant', 'content': content})

        if stop_reason == 'end_turn':
            # Extract any text from the response
            text_parts = [b['text'] for b in content if b.get('type') == 'text']
            text = ' '.join(text_parts).strip()
            self._isAgentLoop = False
            self.responseReceived.emit(text or "Done.")
            self.processingFinished.emit()

        elif stop_reason == 'tool_use':
            # Queue all tool_use blocks for sequential processing
            self._pendingToolUses = [b for b in content if b.get('type') == 'tool_use']
            self._toolResultsForTurn = []

            # Emit any text commentary first
            for b in content:
                if b.get('type') == 'text' and b.get('text', '').strip():
                    self.responseReceived.emit(b['text'])

            # Start processing the first tool
            self._processNextPendingTool()

        else:
            # Unexpected stop reason (e.g. max_tokens)
            self._isAgentLoop = False
            text_parts = [b['text'] for b in content if b.get('type') == 'text']
            text = ' '.join(text_parts).strip()
            self.responseReceived.emit(text or f"Stopped: {stop_reason}")
            self.processingFinished.emit()

    def _processNextPendingTool(self):
        """Process the next queued tool call, or send accumulated results to Claude."""
        if not self._pendingToolUses:
            # All tools in this turn are done — send results back and continue
            self._claudeConversation.append({
                'role': 'user',
                'content': self._toolResultsForTurn
            })
            self._toolResultsForTurn = []
            self._continueAgentLoop()
            return

        # Peek at next tool (don't pop — feedbackToAgent will pop it)
        tool = self._pendingToolUses[0]
        tool_name = tool.get('name', '')
        tool_input = tool.get('input', {})

        print(f"[Claude] Tool call: {tool_name}({tool_input})")

        # Handle the done tool locally — it doesn't need method dispatch
        if tool_name == 'done':
            message = tool_input.get('message', 'Task complete.')
            # Pop from pending and add a synthetic tool result
            self._pendingToolUses.pop(0)
            self._toolResultsForTurn.append({
                'type': 'tool_result',
                'tool_use_id': tool['id'],
                'content': 'Done acknowledged.'
            })
            self._isAgentLoop = False
            self.responseReceived.emit(f"Done: {message}")
            self.processingFinished.emit()
            return

        self.responseReceived.emit(f"Calling: {tool_name}({tool_input})")
        # Emit the method call — do NOT pop yet; feedbackToAgent will pop
        self.methodCallRequested.emit(tool_name, tool_input)
        # processingFinished is NOT emitted here — we wait for feedbackToAgent

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
        match = re.match(r'(\w+)\((.*)\)', command, re.DOTALL)
        if match:
            method_name = match.group(1)
            params_str = match.group(2).strip()

            params = {}
            if params_str:
                # Split on commas that are not inside brackets
                parts = self._splitParams(params_str)
                for param in parts:
                    param = param.strip()
                    if '=' in param:
                        key, value = param.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Try JSON parsing first (handles lists, dicts, bools)
                        try:
                            value = json.loads(value)
                        except (json.JSONDecodeError, ValueError):
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

    @staticmethod
    def _splitParams(s):
        """Split a parameter string on commas, respecting bracket nesting."""
        parts = []
        depth = 0
        current = []
        for ch in s:
            if ch in ('(', '[', '{'):
                depth += 1
                current.append(ch)
            elif ch in (')', ']', '}'):
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current))
        return parts

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
        elif self._backendType == self.BACKEND_CLAUDE:
            return self._testClaudeConnection()
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

    def _testClaudeConnection(self):
        """Test connection to Anthropic Claude API."""
        if not self._claudeApiKey:
            return False, "Anthropic API key not set"
        try:
            # Send a minimal messages request to verify the key works
            url = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": self._claudeModel,
                "max_tokens": 16,
                "messages": [{"role": "user", "content": "hi"}]
            }
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': self._claudeApiKey,
                    'anthropic-version': '2023-06-01'
                }
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                model = result.get('model', self._claudeModel)
                return True, [model]
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "Invalid Anthropic API key"
            body = e.read().decode('utf-8') if e.fp else ''
            return False, f"HTTP {e.code}: {body[:200]}"
        except Exception as e:
            return False, str(e)
