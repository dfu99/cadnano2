"""
rlvr_runner.py

Online RLVR training loop — runs episodes, scores them, updates model weights
after each episode (or every `update_every` episodes), then repeats.

The local model backend (LocalTrainableBackend) is swapped in as
DocumentController._agentBackend while RLVR is running so all existing
method-dispatch and feedbackToAgent wiring in DC works unchanged.

Usage (from agent dialog):
  /rlvr [num_episodes] [max_steps]   — start training loop
  /rlvr-stop                         — halt after current episode
"""

import cadnano2.util as util
util.qtWrapImport('QtCore', globals(), ['QObject', 'QTimer', 'pyqtSignal'])

from .agenttools import RLVR_SCAFFOLD_TOOLS

RLVR_TASK = """\
The design already has helices and scaffold strands placed. Your job is to add \
crossovers and clean up edge fragments so all scaffold strands form ONE CLOSED LOOP.

STARTING STATE (already done for you — do not undo):
  ✓ Helices placed
  ✓ Scaffold strands placed on every helix (full length, e.g. 84 bp)
  ✗ Crossovers not yet added — this is what you must fix

WHY THERE ARE EXPOSED TERMINI AT THE START:
Crossovers can only be placed at specific valid positions inside the helix \
(e.g. index 5 and 68 on an 84 bp helix). After planScaffoldRouting() places \
crossovers there, short edge fragments remain at the ends (positions 0-4 and \
69-83). These have both ends unconnected and must be deleted with \
deleteOrphanFragments(). Strands with one connected end are part of the routing \
and must NOT be deleted.

PROCEDURE (issue ONE tool call per turn, wait for result before next):
1. analyzeDesign() — confirm layout (helices, neighbor pairs, strand counts)
   NOTE: analyzeDesign returns a 'score' field — IGNORE IT. It is NOT the
   scaffold routing reward. Only verifyScaffoldRouting() gives the reward.
2. planScaffoldRouting() — places crossovers at valid positions
3. deleteOrphanFragments() — removes edge fragments (both ends unconnected)
4. verifyScaffoldRouting() — check reward (1.0 = single closed loop = success)
5. If reward < 1.0: analyzeDesign() to see what is still disconnected,
   then planScaffoldRouting() again, then deleteOrphanFragments(), then verify
6. Call done() when reward=1.0 or steps are exhausted

reward=1.0 → single closed loop, success.
reward=0.75 → two loops, one crossover connection missing between them.
reward=0.55 → many loops, planScaffoldRouting() was only partially effective.
"""


class RLVRRunner(QObject):
    """
    Orchestrates the RLVR online training loop.

    Each episode:
      1. Reset design to checkpoint state (undo stack)
      2. Run agent inference via LocalTrainableBackend
      3. Score result with verifyScaffoldRouting()
      4. Update model weights (RWR gradient step)
      5. Repeat

    Weight updates happen every `update_every` episodes (default 1 = every episode).
    More frequent updates → model explores more effectively → success rate rises faster.

    The LocalTrainableBackend is swapped in as dc._agentBackend during the loop
    so DC's _onAgentMethodCall / feedbackToAgent wiring works without changes.

    Signals:
        progressUpdate(str)       — human-readable status per episode
        rlvrFinished(int, int)    — (total_episodes, num_successes) when done
    """

    progressUpdate = pyqtSignal(str)
    rlvrFinished   = pyqtSignal(int, int)

    def __init__(self, dc, logger, verifier, model_id=None, lora_dir=None):
        super().__init__()
        self._dc       = dc
        self._logger   = logger
        self._verifier = verifier

        # Lazy-created on first start
        self._localBackend = None
        self._model_id = model_id
        self._lora_dir = lora_dir

        # State
        self._episode       = 0
        self._num_episodes  = 0
        self._max_steps     = 0
        self._update_every  = 1
        self._successes     = 0
        self._checkpoint_idx = 0
        self._running       = False
        self._pending_trajectories = []   # trajectories awaiting a train step

        # Saved DC state to restore on stop
        self._savedBackend     = None
        self._savedMaxIter     = None
        self._savedAutoApprove = None

    # ==================== PUBLIC API ====================

    def start(self, num_episodes=10, max_steps=15, update_every=1):
        if self._running:
            self.progressUpdate.emit("RLVR already running.")
            return

        self._episode      = 0
        self._num_episodes = num_episodes
        self._max_steps    = max_steps
        self._update_every = max(1, update_every)
        self._successes    = 0
        self._pending_trajectories = []
        self._running      = True

        # Checkpoint the current design state
        self._checkpoint_idx = self._dc.undoStack().index()

        # Create (or reuse) local trainable backend
        if self._localBackend is None:
            from .rlvr_local_backend import LocalTrainableBackend
            self._localBackend = LocalTrainableBackend(
                model_id=self._model_id,
                lora_dir=self._lora_dir,
            )
            self._localBackend.modelReady.connect(self._onModelReady)
            self._localBackend.modelLoadError.connect(self._onModelLoadError)
            self._localBackend.trainStepFinished.connect(self._onTrainStepFinished)
            self._localBackend.processingFinished.connect(self._onEpisodeEnd)
            # Route display and method calls through DC handlers
            self._localBackend.responseReceived.connect(self._dc._onAgentResponse)
            self._localBackend.methodCallRequested.connect(self._dc._onAgentMethodCall)
            self._localBackend.processingStarted.connect(
                lambda: self._dc._agentDialog.setStatus("Processing...")
            )
            self._localBackend.errorOccurred.connect(self._dc._onAgentError)

        # Swap local backend into DC so feedbackToAgent routes correctly
        self._savedBackend     = self._dc._agentBackend
        self._savedMaxIter     = self._savedBackend.MAX_ITERATIONS
        self._savedAutoApprove = self._dc._autoApproveAll

        self._dc._agentBackend = self._localBackend
        self._localBackend.MAX_ITERATIONS = max_steps
        self._dc._autoApproveAll = True

        self.progressUpdate.emit(
            f"Loading local model ({self._localBackend._model_id}) …"
        )
        self._localBackend.loadModel()

    def stop(self):
        """Halt after the current episode and restore DC state."""
        self._running = False
        if self._savedBackend is not None:
            self._dc._agentBackend   = self._savedBackend
            self._savedBackend.MAX_ITERATIONS = self._savedMaxIter
            self._dc._autoApproveAll = self._savedAutoApprove
            self._savedBackend = None

    # ==================== INTERNAL FLOW ====================

    def _onModelReady(self):
        self.progressUpdate.emit("Model ready. Starting episodes…")
        self._startEpisode()

    def _onModelLoadError(self, msg):
        self.progressUpdate.emit(f"Model load failed: {msg}")
        self.stop()

    def _startEpisode(self):
        if not self._running:
            return

        # Reset design to clean checkpoint
        self._dc.undoStack().setIndex(self._checkpoint_idx)

        # Start trajectory logging
        self._logger.startTrajectory(
            task=RLVR_TASK,
            model=self._localBackend.model,
            mode="rlvr",
        )

        ep = self._episode + 1
        n  = self._num_episodes
        self.progressUpdate.emit(f"Episode {ep}/{n} …")

        self._localBackend.processCommand(
            RLVR_TASK, mode="rlvr", tools=RLVR_SCAFFOLD_TOOLS
        )

    def _onEpisodeEnd(self):
        """Fires when backend.processingFinished — score, log, maybe train."""
        if not self._running:
            return

        # Score
        reward_data = self._verifier.getRewardSignal("scaffold_routing")
        reward  = reward_data["reward"]
        success = (reward == 1.0)
        breakdown = reward_data.get("breakdown", {})

        # Finalise trajectory
        self._logger.logVerification(score=reward, valid=success, metrics=breakdown)
        trajectory = self._logger.endTrajectory(success=success)

        if success:
            self._successes += 1
            self._localBackend.saveCheckpoint(f"ep{self._episode + 1}")

        ep = self._episode + 1
        n  = self._num_episodes
        label = "SUCCESS" if success else f"reward={reward:.2f}"
        self.progressUpdate.emit(f"  Episode {ep}/{n}: {label}")

        # Accumulate for batch update
        if trajectory and reward > 0.0:
            self._pending_trajectories.append((trajectory, reward))

        self._episode += 1

        # Train every `update_every` episodes (or at the very end)
        is_last = (self._episode >= self._num_episodes)
        should_train = (
            self._pending_trajectories and
            (self._episode % self._update_every == 0 or is_last)
        )

        if should_train:
            self._runPendingTrainSteps()
        elif is_last:
            self._finish()
        elif self._running:
            QTimer.singleShot(200, self._startEpisode)

    def _runPendingTrainSteps(self):
        """Run one RWR step per pending trajectory sequentially."""
        if not self._pending_trajectories:
            if self._episode >= self._num_episodes:
                self._finish()
            elif self._running:
                QTimer.singleShot(200, self._startEpisode)
            return

        trajectory, reward = self._pending_trajectories.pop(0)
        self.progressUpdate.emit(
            f"  Training step (reward={reward:.2f}, "
            f"{len(self._pending_trajectories)} more pending) …"
        )
        self._localBackend.trainStep(trajectory, reward)
        # _onTrainStepFinished will call _runPendingTrainSteps again

    def _onTrainStepFinished(self, reward, loss):
        self.progressUpdate.emit(f"  → loss={loss:.4f}")
        # Continue draining the queue or move to next episode
        self._runPendingTrainSteps()

    def _finish(self):
        self.stop()
        n   = self._num_episodes
        ok  = self._successes
        pct = (100 * ok // n) if n else 0
        self.progressUpdate.emit(f"\nRLVR done: {ok}/{n} successes ({pct}%)")
        self.rlvrFinished.emit(n, ok)
