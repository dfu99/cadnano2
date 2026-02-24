"""
rlvr_local_backend.py

Local HuggingFace model backend for RLVR: handles inference AND in-process
weight updates so every episode runs on the current trained weights.

Algorithm: Reward-Weighted Regression (RWR)
  For each action step in a trajectory:
    loss_step = cross_entropy(context → tool_call_completion)
  gradient_step scales loss by episode reward:
    total_loss = reward × Σ loss_step
  Higher reward → larger update toward that trajectory.
  Zero reward → no update.

This is intentionally simple. GRPO (group-relative advantages across K rollouts)
is the upgrade path once this is working.

Drop-in interface with AgentBackend:
  Same signals (responseReceived, methodCallRequested, processingFinished, …)
  processCommand(command, mode, tools) / feedbackToAgent(result)
  Additional: modelReady, trainStepFinished(reward, loss)
"""

import json
import os
import re

import cadnano2.util as util
util.qtWrapImport('QtCore', globals(), ['QObject', 'QThread', 'pyqtSignal'])


RLVR_SYSTEM_PROMPT = """\
You are a DNA nanostructure design agent doing scaffold routing.
The design has helices and full-length scaffold strands already placed.
Your job: add crossovers and clean up edge fragments to form ONE CLOSED LOOP.

IMPORTANT: Issue ONE tool call per response. Wait for the result before \
calling the next tool.

Correct procedure:
  1. analyzeDesign() — inspect layout
  2. planScaffoldRouting() — add crossovers
  3. deleteOrphanFragments() — clean up edge fragments
  4. verifyScaffoldRouting() — check reward (THIS is the only success metric)

CRITICAL: analyzeDesign() returns a design quality 'score' — IGNORE IT. \
The ONLY success metric is verifyScaffoldRouting() reward=1.0. \
You must call verifyScaffoldRouting() explicitly to know if routing succeeded.

deleteOrphanFragments() removes only edge fragments where BOTH ends are \
unconnected (no crossover anywhere on that strand). It will not touch strands \
that are part of the routing. Call it after every planScaffoldRouting().\
"""


# ==================== BACKGROUND WORKERS ====================

class _ModelLoader(QThread):
    """Load model + LoRA adapter without blocking the GUI."""

    modelLoaded = pyqtSignal(object, object)   # (model, tokenizer)
    error = pyqtSignal(str)

    def __init__(self, model_id, lora_dir):
        super().__init__()
        self._model_id = model_id
        self._lora_dir = lora_dir

    def run(self):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import LoraConfig, get_peft_model, PeftModel

            print(f"[RLVR] Loading {self._model_id} …")
            tokenizer = AutoTokenizer.from_pretrained(self._model_id)
            model = AutoModelForCausalLM.from_pretrained(
                self._model_id,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )

            adapter_path = os.path.join(self._lora_dir, "adapter_model")
            if os.path.exists(adapter_path):
                print(f"[RLVR] Resuming LoRA from {adapter_path}")
                model = PeftModel.from_pretrained(model, adapter_path, is_trainable=True)
            else:
                print("[RLVR] Initialising fresh LoRA adapter")
                cfg = LoraConfig(
                    r=16,
                    lora_alpha=32,
                    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                    lora_dropout=0.05,
                    bias="none",
                    task_type="CAUSAL_LM",
                )
                model = get_peft_model(model, cfg)
                model.print_trainable_parameters()

            model.train()
            self.modelLoaded.emit(model, tokenizer)

        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")


class _InferenceWorker(QThread):
    """One forward pass (generate) without blocking the GUI."""

    resultReady = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, model, tokenizer, messages, openai_tools, max_new_tokens=512):
        super().__init__()
        self._model = model
        self._tokenizer = tokenizer
        self._messages = messages
        self._tools = openai_tools
        self._max_new_tokens = max_new_tokens

    def run(self):
        try:
            import torch

            text = self._tokenizer.apply_chat_template(
                self._messages,
                tools=self._tools,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)

            with torch.no_grad():
                output = self._model.generate(
                    **inputs,
                    max_new_tokens=self._max_new_tokens,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self._tokenizer.eos_token_id,
                )

            new_tokens = output[0][inputs["input_ids"].shape[1]:]
            response = self._tokenizer.decode(new_tokens, skip_special_tokens=True)
            self.resultReady.emit(response)

        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")


class _TrainWorker(QThread):
    """One RWR gradient step without blocking the GUI."""

    lossReady = pyqtSignal(float)    # total loss
    error = pyqtSignal(str)

    def __init__(self, model, tokenizer, optimizer, trajectory, reward):
        super().__init__()
        self._model = model
        self._tokenizer = tokenizer
        self._optimizer = optimizer
        self._trajectory = trajectory
        self._reward = reward

    def run(self):
        try:
            loss = self._rwr_step()
            self.lossReady.emit(loss)
        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")

    def _rwr_step(self):
        import torch

        reward = self._reward
        actions = self._trajectory.get("actions", [])
        conversation = self._trajectory.get("conversation", [])

        if not actions or reward == 0.0:
            return 0.0

        self._optimizer.zero_grad()
        total_loss = 0.0

        # For each action in the trajectory, build a (context, completion) pair.
        # context  = system + conversation turns up to (but not including) this action
        # completion = the tool call JSON the model should have produced
        for i, action in enumerate(actions):
            method = action.get("method", "")
            params = action.get("params", {})
            if not method:
                continue

            # Conversation entries: [system?, user_task, assistant_call_0,
            #                        user_result_0, assistant_call_1, …]
            # Take everything up to (not including) the assistant turn for action i.
            ctx_turns = conversation[: max(1, i * 2 + 1)]
            # Strip timestamps — tokenizer only needs role/content
            ctx_msgs = [{"role": t["role"], "content": t["content"]} for t in ctx_turns]

            context_text = self._tokenizer.apply_chat_template(
                ctx_msgs, tokenize=False, add_generation_prompt=True
            )
            # qwen3 tool-call completion format
            completion_text = (
                "<tool_call>\n"
                + json.dumps({"name": method, "arguments": params})
                + "\n</tool_call>"
            )

            full_text = context_text + completion_text
            enc = self._tokenizer(
                full_text, return_tensors="pt", truncation=True, max_length=2048
            )
            enc = {k: v.to(self._model.device) for k, v in enc.items()}

            labels = enc["input_ids"].clone()
            # Mask the prompt — supervise only on the completion tokens
            prompt_ids = self._tokenizer(context_text)["input_ids"]
            labels[0, : len(prompt_ids)] = -100

            out = self._model(**enc, labels=labels)
            step_loss = reward * out.loss
            step_loss.backward()
            total_loss += step_loss.item()

        torch.nn.utils.clip_grad_norm_(
            [p for p in self._model.parameters() if p.requires_grad],
            max_norm=1.0,
        )
        self._optimizer.step()
        return total_loss


# ==================== MAIN BACKEND CLASS ====================

class LocalTrainableBackend(QObject):
    """
    Local HuggingFace model backend for the RLVR loop.

    Emits the same signals as AgentBackend so DocumentController's
    _onAgentMethodCall / feedbackToAgent wiring works unchanged.

    Lifecycle:
        backend = LocalTrainableBackend()
        backend.modelReady.connect(start_first_episode)
        backend.loadModel()              # async
        # … each episode:
        backend.processCommand(task, mode="rlvr", tools=RLVR_SCAFFOLD_TOOLS)
        # … when processingFinished fires:
        backend.trainStep(trajectory, reward)
        # … when trainStepFinished fires → start next episode
    """

    # AgentBackend-compatible signals
    responseReceived    = pyqtSignal(str)
    errorOccurred       = pyqtSignal(str)
    processingStarted   = pyqtSignal()
    processingFinished  = pyqtSignal()
    methodCallRequested = pyqtSignal(str, dict)
    agentThinking       = pyqtSignal(str)
    apiKeyNeeded        = pyqtSignal()          # unused; kept for interface compat

    # RLVR-specific signals
    modelReady          = pyqtSignal()
    modelLoadError      = pyqtSignal(str)
    trainStepFinished   = pyqtSignal(float, float)  # (reward, loss)

    MAX_ITERATIONS = 15
    DEFAULT_MODEL_ID = "Qwen/Qwen3-1.7B"
    DEFAULT_LORA_DIR = os.path.expanduser("~/.cadnano2/rlvr_lora")

    def __init__(self, model_id=None, lora_dir=None, parent=None):
        super().__init__(parent)
        self._model_id  = model_id  or self.DEFAULT_MODEL_ID
        self._lora_dir  = lora_dir  or self.DEFAULT_LORA_DIR

        self._model      = None
        self._tokenizer  = None
        self._optimizer  = None
        self._is_loaded  = False

        self._conversation     = []
        self._active_tools     = None   # OpenAI-format tool schemas
        self._iterationCount   = 0
        self._isAgentLoop      = False
        self._pending_calls    = []     # queued tool calls from multi-call responses
        # Keep explicit references to all live workers so Python's GC cannot
        # destroy the QThread object while the underlying OS thread is still
        # running (which causes "QThread: Destroyed while thread still running").
        self._live_workers     = []

        # Expose a `model` property so RLVRRunner can call self._backend.model
        self._model_name = self._model_id
        self._loader = None

    @property
    def model(self):
        return self._model_name

    # ==================== MODEL LOADING ====================

    def loadModel(self):
        """Start async model + LoRA load. Emits modelReady or modelLoadError."""
        if self._is_loaded and self._model is not None and self._tokenizer is not None:
            self.modelReady.emit()
            return
        if self._loader is not None and self._loader.isRunning():
            return

        loader = _ModelLoader(self._model_id, self._lora_dir)
        self._loader = loader
        self._live_workers.append(loader)
        loader.modelLoaded.connect(self._onModelLoaded)
        loader.error.connect(self._onModelLoadError)
        # Retire only when the QThread has actually finished.
        loader.finished.connect(lambda: self._retire_worker(loader))
        loader.start()

    def _onModelLoaded(self, model, tokenizer):
        import torch
        self._model     = model
        self._tokenizer = tokenizer
        self._optimizer = torch.optim.AdamW(
            [p for p in self._model.parameters() if p.requires_grad],
            lr=1e-4,
        )
        self._is_loaded = True
        print(f"[RLVR] Model ready: {self._model_id}")
        self.modelReady.emit()

    def _onModelLoadError(self, msg):
        self.modelLoadError.emit(msg)
        self.errorOccurred.emit(f"Model load failed: {msg}")

    # ==================== INFERENCE (AgentBackend interface) ====================

    def processCommand(self, command, mode="rlvr", tools=None):
        if not self._is_loaded:
            self.errorOccurred.emit("Model not loaded — call loadModel() first.")
            self.processingFinished.emit()
            return

        # Convert Anthropic tool schemas → OpenAI function format for qwen3
        self._active_tools = _anthropic_to_openai_tools(tools) if tools else None

        self._iterationCount = 0
        self._isAgentLoop    = True
        self._pending_calls  = []
        self._conversation   = [
            {"role": "system",  "content": RLVR_SYSTEM_PROMPT},
            {"role": "user",    "content": command},
        ]

        self.processingStarted.emit()
        self._continueLoop()

    def feedbackToAgent(self, result):
        """Receive method execution result and continue the agent loop."""
        if not self._isAgentLoop:
            return
        self._conversation.append({"role": "user", "content": f"Result: {result}"})
        # If the previous response queued more tool calls, execute the next one
        # without asking the model again (saves an inference step)
        if self._pending_calls:
            tool_name, tool_args = self._pending_calls.pop(0)
            print(f"[RLVR] executing queued call: {tool_name}({tool_args})")
            self._dispatch_tool(tool_name, tool_args)
            return
        self._continueLoop()

    def _continueLoop(self):
        self._iterationCount += 1
        if self._iterationCount > self.MAX_ITERATIONS:
            self._isAgentLoop = False
            self.responseReceived.emit(
                f"Stopped: max iterations ({self.MAX_ITERATIONS})"
            )
            self.processingFinished.emit()
            return

        worker = _InferenceWorker(
            self._model, self._tokenizer, self._conversation, self._active_tools
        )
        self._live_workers.append(worker)
        worker.resultReady.connect(self._handleResponse)
        worker.error.connect(self._handleError)
        # Retire only when the QThread has actually finished.
        worker.finished.connect(lambda: self._retire_worker(worker))
        worker.start()

    def _handleResponse(self, response):
        self._conversation.append({"role": "assistant", "content": response})
        print(f"[RLVR] iter={self._iterationCount} raw response ({len(response)}c): "
              f"{response[:300]!r}")

        all_calls = _parse_all_tool_calls(response)
        if all_calls:
            # Queue all calls after the first; execute first now
            self._pending_calls = list(all_calls[1:])
            tool_name, tool_args = all_calls[0]
            self._dispatch_tool(tool_name, tool_args)
            return

        # No tool call — emit text and nudge the model
        self.responseReceived.emit(response)
        self._conversation.append({
            "role": "user",
            "content": (
                "Please use a tool. Call verifyScaffoldRouting() to check current state, "
                "or call done() if finished."
            ),
        })
        self._continueLoop()

    def _dispatch_tool(self, tool_name, tool_args):
        """Execute one tool call; stop loop if 'done', otherwise wait for feedbackToAgent."""
        if tool_name == "done":
            self._isAgentLoop = False
            self._pending_calls = []
            msg = (tool_args.get("message", "Task complete.")
                   if isinstance(tool_args, dict) else str(tool_args))
            self.responseReceived.emit(f"Done: {msg}")
            self.processingFinished.emit()
            return
        self.responseReceived.emit(f"Calling: {tool_name}({tool_args})")
        self.methodCallRequested.emit(tool_name, tool_args)
        # do NOT emit processingFinished — wait for feedbackToAgent

    def _retire_worker(self, worker):
        """Remove worker from live set and schedule Qt-side deletion.
        Called only after the thread has fully finished, so deleteLater is safe."""
        if worker in self._live_workers:
            self._live_workers.remove(worker)
        if worker is self._loader:
            self._loader = None
        worker.deleteLater()

    def _handleError(self, msg):
        self._isAgentLoop = False
        self.errorOccurred.emit(msg)
        self.processingFinished.emit()

    # ==================== TRAINING ====================

    def trainStep(self, trajectory, reward):
        """
        Run one RWR gradient step on the completed trajectory.
        Emits trainStepFinished(reward, loss) when done.
        Saves LoRA weights after each step.
        """
        if not self._is_loaded:
            return

        if reward == 0.0:
            # Zero reward gives zero gradient — skip the compute but still signal done
            print("[RLVR] Reward=0.0 — skipping gradient step")
            self.trainStepFinished.emit(0.0, 0.0)
            return

        worker = _TrainWorker(
            self._model, self._tokenizer, self._optimizer, trajectory, reward
        )
        self._live_workers.append(worker)
        worker.lossReady.connect(lambda loss: self._onTrainDone(reward, loss))
        worker.error.connect(lambda e: print(f"[RLVR] Train error: {e}"))
        # Retire only when the QThread has actually finished.
        worker.finished.connect(lambda: self._retire_worker(worker))
        worker.start()

    def _onTrainDone(self, reward, loss):
        os.makedirs(self._lora_dir, exist_ok=True)
        adapter_path = os.path.join(self._lora_dir, "adapter_model")
        self._model.save_pretrained(adapter_path)
        print(f"[RLVR] Train step: reward={reward:.3f} loss={loss:.4f} → {adapter_path}")
        self.trainStepFinished.emit(reward, loss)

    def saveCheckpoint(self, tag):
        """Save a numbered checkpoint (call after episodes of interest)."""
        ckpt = os.path.join(self._lora_dir, f"ckpt_{tag}")
        os.makedirs(ckpt, exist_ok=True)
        self._model.save_pretrained(ckpt)
        print(f"[RLVR] Checkpoint: {ckpt}")


# ==================== HELPERS ====================

def _anthropic_to_openai_tools(anthropic_tools):
    """Convert Anthropic tool schemas to OpenAI function-call format for qwen3."""
    if not anthropic_tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in anthropic_tools
    ]


def _parse_all_tool_calls(text):
    """
    Extract ALL (tool_name, args_dict) tuples from a model response.

    Handles:
      <tool_call>{"name": "foo", "arguments": {...}}</tool_call>  (qwen3 native, 1+)
      {"method": "foo", "params": {...}}   (fallback / Ollama format)
      {"done": true, "message": "…"}

    Returns a list of (name, args) tuples in document order.
    """
    calls = []

    # qwen3 native: find ALL <tool_call>…</tool_call> blocks
    for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL):
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict) and "name" in obj:
                calls.append((obj["name"], obj.get("arguments", {})))
        except json.JSONDecodeError:
            pass

    if calls:
        return calls

    # Fallback: scan for JSON objects with "method" or "done" keys
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start:i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        if "method" in obj:
                            calls.append((obj["method"], obj.get("params", {})))
                        elif obj.get("done"):
                            calls.append(("done", {"message": obj.get("message", "Done.")}))
                except json.JSONDecodeError:
                    pass
                start = None

    return calls
