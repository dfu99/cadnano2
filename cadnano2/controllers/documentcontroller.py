import io
import os
from ..cadnano import app
from ..model.document import Document
from ..model.io.decoder import decode
from ..model.io.encoder import encode
from ..views.documentwindow import DocumentWindow
from ..views import styles
import cadnano2.util as util
util.qtWrapImport('QtCore', globals(), ['QDir', 'QFileInfo', 'QRect',
                                        'QSettings',
                                        'QSize', 'Qt'])
util.qtWrapImport('QtGui', globals(), [
                                       'QAction',
                                       'QIcon',
                                       'QKeySequence',
                                       'QPainter'
                                       ])
util.qtWrapImport('QtWidgets', globals(), ['QApplication',
                                           'QDialog',
                                           'QDockWidget',
                                           'QFileDialog',
                                           'QGraphicsItem',
                                           'QMainWindow',
                                           'QMessageBox',
                                           'QStyleOptionGraphicsItem'])
util.qtWrapImport('QtSvg', globals(), ['QSvgGenerator'])

from ..views.agent.agentdialog import AgentDialog
from ..views.agent.agentbackend import AgentBackend
from ..views.agent.agentmethods import AgentMethods
from ..views.agent.agentverifier import DesignVerifier
from ..views.agent.trajectorylogger import TrajectoryLogger


class DocumentController():
    """
    Connects UI buttons to their corresponding actions in the model.
    """
    ### INIT METHODS ###
    def __init__(self):
        """docstring for __init__"""
        # initialize variables
        self._document = Document()
        self._document.setController(self)
        self._activePart = None
        self._filename = None
        self._fileOpenPath = None  # will be set in _readSettings
        self._hasNoAssociatedFile = True
        self._pathViewInstance = None
        self._sliceViewInstance = None
        self._undoStack = None
        self.win = None
        self.fileopendialog = None
        self.filesavedialog = None

        self.settings = QSettings()
        self._readSettings()

        QDir.addSearchPath('icons', 'ui/mainwindow/images/')

        # call other init methods
        self._initWindow()
        if app().isInMaya():
            self._initMaya()
        app().documentControllers.add(self)

    def _initWindow(self):
        """docstring for initWindow"""
        self.win = DocumentWindow(docCtrlr=self)
        self.win.setWindowIcon(QIcon('icons:cadnano2-app-icon.png'))
        app().documentWindowWasCreatedSignal.emit(self._document, self.win)
        self._connectWindowSignalsToSelf()
        self._initAgentDialog()
        self.win.show()

    def _initMaya(self):
        """
        Initialize Maya-related state. Delete Maya nodes if there
        is an old document left over from the same session. Set up
        the Maya window.
        """
        # There will only be one document
        if (app().activeDocument and app().activeDocument.win and
                                not app().activeDocument.win.close()):
            return
        del app().activeDocument
        app().activeDocument = self

        import maya.OpenMayaUI as OpenMayaUI
        import sip
        ptr = OpenMayaUI.MQtUtil.mainWindow()
        mayaWin = sip.wrapinstance(int(ptr), QMainWindow)
        self.windock = QDockWidget("Cadnano2")
        self.windock.setFeatures(QDockWidget.DockWidgetMovable
                                 | QDockWidget.DockWidgetFloatable)
        self.windock.setAllowedAreas(Qt.LeftDockWidgetArea
                                     | Qt.RightDockWidgetArea)
        self.windock.setWidget(self.win)
        mayaWin.addDockWidget(Qt.DockWidgetArea(Qt.LeftDockWidgetArea),
                                self.windock)
        self.windock.setVisible(True)

    def _initAgentDialog(self):
        """Initialize the agent dialog overlay and backend."""
        # Create agent components
        self._agentDialog = AgentDialog(self.win)
        self._agentBackend = AgentBackend(self.win)
        self._agentMethods = AgentMethods(self)
        self._agentVerifier = DesignVerifier(self)
        self._trajectoryLogger = TrajectoryLogger(parent=self.win)

        # Approval mode state
        self._awaitingApproval = False
        self._awaitingCorrection = False
        self._autoApproveAll = False
        self._preCorrectionState = None
        self._lastActionMethod = None
        self._lastActionParams = None
        self._lastActionResult = None

        # Connect agent signals
        self._agentDialog.commandSubmitted.connect(self._onAgentCommand)
        self._agentDialog.backendChanged.connect(self._onBackendChanged)
        self._agentBackend.responseReceived.connect(self._onAgentResponse)
        self._agentBackend.methodCallRequested.connect(self._onAgentMethodCall)
        print("[Agent] Signal connections established")
        self._agentBackend.processingStarted.connect(
            lambda: self._agentDialog.setStatus("Processing...")
        )
        self._agentBackend.processingFinished.connect(self._onAgentFinished)
        self._agentBackend.errorOccurred.connect(self._onAgentError)

        # Connect approval signals
        self._agentDialog.actionApproved.connect(self._onActionApproved)
        self._agentDialog.actionApproveAll.connect(self._onActionApproveAll)
        self._agentDialog.actionCorrectionRequested.connect(self._onActionCorrect)

        # Connect API key signals
        self._agentDialog.apiKeySubmitted.connect(self._onApiKeySubmitted)
        self._agentBackend.apiKeyNeeded.connect(self._onApiKeyNeeded)

        # Initialize backend from saved dialog setting
        self._onBackendChanged(self._agentDialog.backend())

        # Create keyboard shortcut (Ctrl+I / Cmd+I)
        self._agentAction = QAction("Toggle Agent Dialog", self.win)
        self._agentAction.setShortcut(QKeySequence("Ctrl+I"))
        self._agentAction.triggered.connect(self._toggleAgentDialog)
        self.win.addAction(self._agentAction)

    def _toggleAgentDialog(self):
        """Show or hide the agent dialog."""
        if self._agentDialog.isVisible():
            self._agentDialog.hideDialog()
        else:
            self._agentDialog.positionRelativeToParent()
            self._agentDialog.showDialog()

    def _onBackendChanged(self, backend):
        """Handle backend change from dialog."""
        if backend == "openai":
            self._agentBackend.setBackend("openai", model="gpt-5")
            # If no API key is available, prompt for one
            if not self._agentBackend.openaiApiKey:
                self._agentDialog.showApiKeyPrompt()
        else:
            self._agentBackend.setBackend("ollama", model="qwen3:1.7b")

    def _onApiKeyNeeded(self):
        """Handle backend requesting an API key."""
        self._agentDialog.showApiKeyPrompt()

    def _onApiKeySubmitted(self, api_key):
        """Handle API key submitted from dialog."""
        from cadnano2.views.agent.agentbackend import AgentBackend
        AgentBackend.saveApiKey(api_key)
        self._agentBackend.openaiApiKey = api_key
        self._agentDialog.setStatus("API key saved. You can now use the OpenAI backend.")

    def _listTrajectories(self):
        """List available trajectories."""
        trajectories = self._trajectoryLogger.listTrajectories()
        if not trajectories:
            self._agentDialog.setStatus("No trajectories found.")
            return

        lines = ["Available trajectories:", ""]
        for traj in trajectories[:20]:  # Show latest 20
            score = traj.get('score') or 0
            actions = traj.get('action_count', 0)
            task = traj.get('task', '')[:50]
            lines.append(f"  {traj['id']} [{traj['category']}] score={score:.2f} actions={actions}")
            lines.append(f"    Task: {task}...")
            lines.append("")

        lines.append("Use '/replay <trajectory_id>' to replay a trajectory.")
        self._agentDialog.setStatus('\n'.join(lines))

    def _replayTrajectory(self, trajectory_id):
        """Replay a saved trajectory."""
        info = self._trajectoryLogger.getTrajectoryInfo(trajectory_id)
        if info is None:
            self._agentDialog.setStatus(f"Trajectory not found: {trajectory_id}")
            return

        actions = self._trajectoryLogger.getReplayActions(trajectory_id)
        if not actions:
            self._agentDialog.setStatus(f"No actions in trajectory: {trajectory_id}")
            return

        # Show trajectory info
        lines = [
            f"Replaying trajectory: {trajectory_id}",
            f"Task: {info.get('task', 'N/A')}",
            f"Actions: {info.get('action_count', 0)}",
            f"Original score: {info.get('final_score', 'N/A')}",
            "",
            "Executing actions...",
            ""
        ]
        self._agentDialog.setStatus('\n'.join(lines))

        # Execute each action with a small delay for visibility
        from PyQt6.QtCore import QTimer

        self._replayActions = actions
        self._replayIndex = 0
        self._replayLines = lines

        # Start replay loop
        QTimer.singleShot(500, self._executeNextReplayAction)

    def _executeNextReplayAction(self):
        """Execute the next action in replay sequence."""
        from PyQt6.QtCore import QTimer

        if self._replayIndex >= len(self._replayActions):
            # Replay complete - run verification
            self._replayLines.append("")
            self._replayLines.append("Replay complete. Running verification...")
            self._agentDialog.setStatus('\n'.join(self._replayLines))

            # Verify the result
            verification = self._agentVerifier.getRewardSignal()
            self._replayLines.append(f"Final score: {verification['reward']:.2f}")
            self._replayLines.append(f"Valid: {verification['valid']}")
            if verification['breakdown'].get('issues'):
                for issue in verification['breakdown']['issues']:
                    self._replayLines.append(f"  Issue: {issue}")
            self._agentDialog.setStatus('\n'.join(self._replayLines))
            return

        method_name, params = self._replayActions[self._replayIndex]
        self._replayIndex += 1

        # Execute the method
        self._replayLines.append(f"[{self._replayIndex}] {method_name}({params})")
        self._agentDialog.setStatus('\n'.join(self._replayLines))

        success, result = self._agentMethods.executeMethod(method_name, params)
        status = "OK" if success else "FAILED"
        self._replayLines.append(f"    -> {status}: {result[:80]}...")

        self._agentDialog.setStatus('\n'.join(self._replayLines))

        # Schedule next action
        QTimer.singleShot(300, self._executeNextReplayAction)

    def _onAgentCommand(self, command):
        """Forward command to the agent backend."""
        mode = self._agentDialog.mode()

        # Handle correction mode: user has made their fix and described it
        if self._awaitingCorrection:
            self._handleCorrectionSubmitted(command)
            return

        # Check for special replay commands
        if command.startswith("/replay "):
            trajectory_id = command[8:].strip()
            self._replayTrajectory(trajectory_id)
            return
        elif command == "/list" or command == "/trajectories":
            self._listTrajectories()
            return

        # Reset auto-approve for new trajectory
        self._autoApproveAll = False

        # Start trajectory logging for Edit mode
        if mode == "edit":
            self._trajectoryLogger.startTrajectory(
                task=command,
                model=self._agentBackend.model,
                mode=mode
            )
            self._trajectoryLogger.logConversation("user", command)

        self._agentBackend.processCommand(command, mode)

    def _onAgentResponse(self, response):
        """Display response in the agent dialog."""
        self._agentDialog.setStatus(response)

        # Log assistant response
        if self._trajectoryLogger.isRecording():
            self._trajectoryLogger.logConversation("assistant", response)

    def _onAgentMethodCall(self, methodName, params):
        """Execute a method requested by the agent with validation."""
        print(f"[Agent] Method call received: {methodName}({params})")

        # Pre-execution validation
        is_valid, validation_msg, suggestions = self._agentVerifier.validateAction(methodName, params)
        print(f"[Agent] Validation: valid={is_valid}, msg={validation_msg}")

        if not is_valid:
            # Action would fail - provide feedback without executing
            result_msg = f"Validation failed: {validation_msg}"
            if suggestions:
                result_msg += f" Suggestions: {suggestions}"
            self._agentDialog.setStatus(f"[{methodName}] {result_msg}")

            # Log failed action
            if self._trajectoryLogger.isRecording():
                self._trajectoryLogger.logAction(
                    method_name=methodName,
                    params=params,
                    result=result_msg,
                    success=False,
                    validation_msg=validation_msg
                )

            self._agentBackend.feedbackToAgent(result_msg)
            return

        # Execute the method
        success, result = self._agentMethods.executeMethod(methodName, params)
        print(f"[Agent] Execution: success={success}, result={result}")

        # Format result message
        if success:
            result_msg = str(result)
            # Add validation warnings if any
            if validation_msg and "Warning" in validation_msg:
                result_msg += f" ({validation_msg})"
        else:
            result_msg = f"Error: {result}"

        self._agentDialog.setStatus(f"[{methodName}] {result_msg}")

        # Log the action
        if self._trajectoryLogger.isRecording():
            self._trajectoryLogger.logAction(
                method_name=methodName,
                params=params,
                result=result_msg,
                success=success,
                validation_msg=validation_msg if validation_msg else None
            )

            # If this was a verification method, log verification result
            if methodName in ('verifyDesign', 'verify6HelixBundle') and success:
                # Parse verification result from the method result
                verification = self._agentVerifier.getRewardSignal(
                    structure_type='6-helix' if '6' in methodName else None
                )
                self._trajectoryLogger.logVerification(
                    score=verification['reward'],
                    valid=verification['valid'],
                    metrics=verification['breakdown']['metrics']
                )

        # Check if this is a modifying action that needs approval
        # Query methods don't need approval, only actions that change the design
        query_methods = {
            'listHelices', 'listStrands', 'getStrandAt', 'getActivePartInfo',
            'getHelixInfo', 'getHelixDirection', 'getHoneycombPositions',
            'getPotentialCrossovers', 'getValidCrossoverPositions',
            'getSelectedStrands', 'verifyDesign', 'verify6HelixBundle',
            'getPartSize', 'listCrossovers',
            'selectStrand', 'selectEndpoint', 'selectCrossover', 'clearSelection',
            # Level 2 query tools
            'describeHelix', 'analyzeDesign', 'suggestCrossovers', 'getNeighborPairs'
        }

        if success and methodName not in query_methods:
            # Store action info for approval flow
            self._lastActionMethod = methodName
            self._lastActionParams = params
            self._lastActionResult = result_msg

            if self._autoApproveAll:
                # Auto-approve: log and continue without prompting
                if self._trajectoryLogger.isRecording():
                    self._trajectoryLogger.logConversation(
                        "user",
                        f"[AUTO-APPROVED] {methodName}"
                    )
                result_msg = f"{result_msg} [Auto-approved]"
                self._agentBackend.feedbackToAgent(result_msg)
                return

            self._awaitingApproval = True

            # Show approval buttons - user will see result in GUI
            action_desc = f"{methodName}({params})"
            self._agentDialog.showApprovalButtons(action_desc)

            # Pause the agent loop - don't feed back yet
            # The approval handler will continue the loop
            print("[Agent] Awaiting user approval...")
            return

        # For query methods or failed actions, continue the agent loop immediately
        self._agentBackend.feedbackToAgent(result_msg)

    def _onAgentFinished(self):
        """Handle agent processing completion."""
        if self._trajectoryLogger.isRecording():
            # Get final verification score
            verification = self._agentVerifier.getRewardSignal()
            self._trajectoryLogger.logVerification(
                score=verification['reward'],
                valid=verification['valid'],
                metrics=verification['breakdown']['metrics']
            )

            # End and save trajectory
            trajectory = self._trajectoryLogger.endTrajectory(success=True)
            if trajectory:
                score = trajectory.get('final_score', 0) or 0
                action_count = len(trajectory.get('actions', []))
                print(f"Trajectory completed: {action_count} actions, score: {score:.2f}")

    def _onAgentError(self, error_msg):
        """Handle agent error."""
        if self._trajectoryLogger.isRecording():
            # Log error and end trajectory
            self._trajectoryLogger.logConversation("system", f"Error: {error_msg}")
            trajectory = self._trajectoryLogger.endTrajectory(success=False, error=error_msg)
            if trajectory:
                print(f"Trajectory ended with error: {error_msg}")

    def _onActionApproved(self):
        """Handle user approving an action."""
        print("[Agent] Action approved by user")

        # Log approval decision
        if self._trajectoryLogger.isRecording():
            self._trajectoryLogger.logConversation(
                "user",
                f"[APPROVED] {self._lastActionMethod}"
            )

        # Reset approval state
        self._awaitingApproval = False

        # Continue the agent loop with positive feedback
        result_msg = f"{self._lastActionResult} [User approved]"
        self._agentBackend.feedbackToAgent(result_msg)

    def _onActionApproveAll(self):
        """Handle user approving all remaining actions in this trajectory."""
        print("[Agent] Approve All selected by user")
        self._autoApproveAll = True

        # Log and continue as a normal approval
        if self._trajectoryLogger.isRecording():
            self._trajectoryLogger.logConversation(
                "user",
                f"[APPROVE ALL] {self._lastActionMethod}"
            )

        self._awaitingApproval = False

        result_msg = f"{self._lastActionResult} [User approved all]"
        self._agentBackend.feedbackToAgent(result_msg)

    def _onActionCorrect(self):
        """Handle user wanting to correct/refine an action."""
        print("[Agent] Action correction requested by user")

        # Undo the wrong action first
        undo_stack = self.undoStack()
        if undo_stack and undo_stack.canUndo():
            undo_stack.undo()
            self._agentDialog.appendStatus("\n[Correct] Wrong action undone.")
        else:
            self._agentDialog.appendStatus("\n[Correct] Nothing to undo.")

        # Log correction request and undo
        if self._trajectoryLogger.isRecording():
            self._trajectoryLogger.logConversation(
                "user",
                f"[CORRECTION REQUESTED] {self._lastActionMethod}"
            )
            self._trajectoryLogger.logAction(
                method_name=self._lastActionMethod,
                params=self._lastActionParams,
                result="Undone by user for correction",
                success=False,
                validation_msg="User corrected this action"
            )

        # Capture pre-correction state snapshot
        self._preCorrectionState = self._captureDesignState()

        # Enter correction mode and let user act in the GUI
        self._awaitingApproval = False
        self._awaitingCorrection = True

        self._agentDialog.appendStatus(
            "\n[Correct] Make your correction in the GUI, then describe "
            "what you did below and press Enter."
        )

    def _captureDesignState(self):
        """Capture the current design state as a string for diffing."""
        parts = []
        success, helices = self._agentMethods.executeMethod('listHelices', {})
        if success:
            parts.append(f"Helices:\n{helices}")
        success, strands = self._agentMethods.executeMethod('listStrands', {})
        if success:
            parts.append(f"Strands:\n{strands}")
        return "\n\n".join(parts)

    def _handleCorrectionSubmitted(self, user_description):
        """Handle user submitting their correction description."""
        print(f"[Agent] Correction submitted: {user_description}")
        self._awaitingCorrection = False

        # Capture post-correction state
        post_state = self._captureDesignState()

        # Log the user's correction description
        if self._trajectoryLogger.isRecording():
            self._trajectoryLogger.logConversation(
                "user",
                f"[CORRECTION] {user_description}"
            )

        # Build diff feedback for the agent
        pre = self._preCorrectionState or "(no state captured)"
        feedback = (
            f"User rejected the last action ({self._lastActionMethod}) and "
            f"performed a manual correction.\n\n"
            f"User's description of correction: {user_description}\n\n"
            f"State BEFORE correction:\n{pre}\n\n"
            f"State AFTER correction:\n{post_state}\n\n"
            f"Based on the diff above, respond with the single JSON method "
            f"call that would reproduce the user's correction. Then continue "
            f"with any remaining steps."
        )

        self._preCorrectionState = None
        self._agentDialog.appendStatus("\n[Correct] Correction captured. Resuming agent...")

        # Resume the agent loop with the diff feedback
        self._agentBackend.feedbackToAgent(feedback)

    def destroyDC(self):
        self.disconnectSignalsToSelf()
        if self.win is not None:
            self.win.destroyWin()
            self.win = None
    # end def

    def disconnectSignalsToSelf(self):
        win = self.win
        if win is not None:
            win.actionNew.triggered.disconnect(self.actionNewSlot)
            win.actionOpen.triggered.disconnect(self.actionOpenSlot)
            win.actionDrop.triggered.disconnect(self.actionDropSlot)
            win.actionClose.triggered.disconnect(self.actionCloseSlot)
            win.actionSave.triggered.disconnect(self.actionSaveSlot)
            win.actionSave_As.triggered.disconnect(self.actionSaveAsSlot)
            win.actionSVG.triggered.disconnect(self.actionSVGSlot)
            win.actionAutoStaple.triggered.disconnect(self.actionAutostapleSlot)
            win.actionExportStaples.triggered.disconnect(self.actionExportStaplesSlot)
            win.actionPreferences.triggered.disconnect(self.actionPrefsSlot)
            win.actionModify.triggered.disconnect(self.actionModifySlot)
            win.actionNewHoneycombPart.triggered.disconnect(self.actionAddHoneycombPartSlot)
            win.actionNewSquarePart.triggered.disconnect(self.actionAddSquarePartSlot)
            win.closeEvent = self.windowCloseEventHandler
            win.actionAbout.triggered.disconnect(self.actionAboutSlot)
            win.actionCadnanoWebsite.triggered.disconnect(self.actionCadnanoWebsiteSlot)
            win.actionFeedback.triggered.disconnect(self.actionFeedbackSlot)
            win.actionFilterHandle.triggered.disconnect(self.actionFilterHandleSlot)
            win.actionFilterEndpoint.triggered.disconnect(self.actionFilterEndpointSlot)
            win.actionFilterStrand.triggered.disconnect(self.actionFilterStrandSlot)
            win.actionFilterXover.triggered.disconnect(self.actionFilterXoverSlot)
            win.actionFilterScaf.triggered.disconnect(self.actionFilterScafSlot)
            win.actionFilterStap.triggered.disconnect(self.actionFilterStapSlot)
            win.actionRenumber.triggered.disconnect(self.actionRenumberSlot)
        # Disconnect agent signals
        if hasattr(self, '_agentDialog') and self._agentDialog is not None:
            self._agentDialog.commandSubmitted.disconnect(self._onAgentCommand)
        if hasattr(self, '_agentBackend') and self._agentBackend is not None:
            self._agentBackend.responseReceived.disconnect(self._onAgentResponse)
            self._agentBackend.methodCallRequested.disconnect(self._onAgentMethodCall)
            self._agentBackend.processingFinished.disconnect(self._onAgentFinished)
            self._agentBackend.errorOccurred.disconnect(self._onAgentError)
        if hasattr(self, '_agentAction') and self._agentAction is not None:
            self._agentAction.triggered.disconnect(self._toggleAgentDialog)
        if hasattr(self, '_trajectoryLogger') and self._trajectoryLogger is not None:
            # Cancel any in-progress trajectory
            self._trajectoryLogger.cancelTrajectory()
    # end def

    def _connectWindowSignalsToSelf(self):
        """This method serves to group all the signal & slot connections
        made by DocumentController"""
        self.win.actionNew.triggered.connect(self.actionNewSlot)
        self.win.actionOpen.triggered.connect(self.actionOpenSlot)
        self.win.actionDrop.triggered.connect(self.actionDropSlot)
        self.win.actionClose.triggered.connect(self.actionCloseSlot)
        self.win.actionSave.triggered.connect(self.actionSaveSlot)
        self.win.actionSave_As.triggered.connect(self.actionSaveAsSlot)
        self.win.actionSVG.triggered.connect(self.actionSVGSlot)
        self.win.actionAutoStaple.triggered.connect(self.actionAutostapleSlot)
        self.win.actionExportStaples.triggered.connect(self.actionExportStaplesSlot)
        self.win.actionPreferences.triggered.connect(self.actionPrefsSlot)
        self.win.actionModify.triggered.connect(self.actionModifySlot)
        self.win.actionNewHoneycombPart.triggered.connect(self.actionAddHoneycombPartSlot)
        self.win.actionNewSquarePart.triggered.connect(self.actionAddSquarePartSlot)
        self.win.closeEvent = self.windowCloseEventHandler
        self.win.actionAbout.triggered.connect(self.actionAboutSlot)
        self.win.actionCadnanoWebsite.triggered.connect(self.actionCadnanoWebsiteSlot)
        self.win.actionFeedback.triggered.connect(self.actionFeedbackSlot)
        self.win.actionFilterHandle.triggered.connect(self.actionFilterHandleSlot)
        self.win.actionFilterEndpoint.triggered.connect(self.actionFilterEndpointSlot)
        self.win.actionFilterStrand.triggered.connect(self.actionFilterStrandSlot)
        self.win.actionFilterXover.triggered.connect(self.actionFilterXoverSlot)
        self.win.actionFilterScaf.triggered.connect(self.actionFilterScafSlot)
        self.win.actionFilterStap.triggered.connect(self.actionFilterStapSlot)
        self.win.actionRenumber.triggered.connect(self.actionRenumberSlot)


    ### SLOTS ###
    def undoStackCleanChangedSlot(self):
        """The title changes to include [*] on modification."""
        self.win.setWindowModified(not self.undoStack().isClean())
        self.win.setWindowTitle(self.documentTitle())

    def actionAboutSlot(self):
        """Displays the about cadnano dialog."""
        from cadnano2.ui.dialogs.ui_about import Ui_About
        dialog = QDialog()
        dialogAbout = Ui_About()  # reusing this dialog, should rename
        dialog.setStyleSheet("QDialog { background-image: url(ui/dialogs/images/cadnano2-about.png); background-repeat: none; }")
        dialogAbout.setupUi(dialog)
        dialog.exec()

    filterList = ["strand", "endpoint", "xover", "virtualHelix"]
    def actionFilterHandleSlot(self):
        """Disables all other selection filters when active."""
        fH = self.win.actionFilterHandle
        fE = self.win.actionFilterEndpoint
        fS = self.win.actionFilterStrand
        fX = self.win.actionFilterXover
        fH.setChecked(True)
        if fE.isChecked():
            fE.setChecked(False)
        if fS.isChecked():
            fS.setChecked(False)
        if fX.isChecked():
            fX.setChecked(False)
        self._document.documentSelectionFilterChangedSignal.emit(["virtualHelix"])

    def actionFilterEndpointSlot(self):
        """
        Disables handle filters when activated.
        Remains checked if no other item-type filter is active.
        """
        fH = self.win.actionFilterHandle
        fE = self.win.actionFilterEndpoint
        fS = self.win.actionFilterStrand
        fX = self.win.actionFilterXover
        if fH.isChecked():
            fH.setChecked(False)
        if not fS.isChecked() and not fX.isChecked():
            fE.setChecked(True)
        self._strandFilterUpdate()
    # end def

    def actionFilterStrandSlot(self):
        """
        Disables handle filters when activated.
        Remains checked if no other item-type filter is active.
        """
        fH = self.win.actionFilterHandle
        fE = self.win.actionFilterEndpoint
        fS = self.win.actionFilterStrand
        fX = self.win.actionFilterXover
        if fH.isChecked():
            fH.setChecked(False)
        if not fE.isChecked() and not fX.isChecked():
            fS.setChecked(True)
        self._strandFilterUpdate()
    # end def

    def actionFilterXoverSlot(self):
        """
        Disables handle filters when activated.
        Remains checked if no other item-type filter is active.
        """
        fH = self.win.actionFilterHandle
        fE = self.win.actionFilterEndpoint
        fS = self.win.actionFilterStrand
        fX = self.win.actionFilterXover
        if fH.isChecked():
            fH.setChecked(False)
        if not fE.isChecked() and not fS.isChecked():
            fX.setChecked(True)
        self._strandFilterUpdate()
    # end def

    def actionFilterScafSlot(self):
        """Remains checked if no other strand-type filter is active."""
        fSc = self.win.actionFilterScaf
        fSt = self.win.actionFilterStap
        if not fSc.isChecked() and not fSt.isChecked():
            fSc.setChecked(True)
        self._strandFilterUpdate()

    def actionFilterStapSlot(self):
        """Remains checked if no other strand-type filter is active."""
        fSc = self.win.actionFilterScaf
        fSt = self.win.actionFilterStap
        if not fSc.isChecked() and not fSt.isChecked():
            fSt.setChecked(True)
        self._strandFilterUpdate()
    # end def

    def _strandFilterUpdate(self):
        win = self.win
        filterList = []
        if win.actionFilterEndpoint.isChecked():
            filterList.append("endpoint")
        if win.actionFilterStrand.isChecked():
            filterList.append("strand")
        if win.actionFilterXover.isChecked():
            filterList.append("xover")
        if win.actionFilterScaf.isChecked():
            filterList.append("scaffold")
        if win.actionFilterStap.isChecked():
            filterList.append("staple")
        self._document.documentSelectionFilterChangedSignal.emit(filterList)
    # end def

    def actionNewSlot(self):
        """
        1. If document is has no parts, do nothing.
        2. If document is dirty, call maybeSave and continue if it succeeds.
        3. Create a new document and swap it into the existing ctrlr/window.
        """
        # clear/reset the view!

        if len(self._document.parts()) == 0:
            return  # no parts
        if self.maybeSave() == False:
            return  # user canceled in maybe save
        else:  # user did not cancel
            if self.filesavedialog != None:
                self.filesavedialog.finished.connect(self.newClickedCallback)
            else:  # user did not save
                self.newClickedCallback()  # finalize new

    def actionOpenSlot(self):
        """
        1. If document is untouched, proceed to open dialog.
        2. If document is dirty, call maybesave and continue if it succeeds.
        Downstream, the file is selected in openAfterMaybeSave,
        and the selected file is actually opened in openAfterMaybeSaveCallback.
        """
        if self.maybeSave() == False:
            return  # user canceled in maybe save
        else:  # user did not cancel
            if hasattr(self, "filesavedialog"): # user did save
                if self.filesavedialog != None:
                    self.filesavedialog.finished.connect(self.openAfterMaybeSave)
                else:
                    self.openAfterMaybeSave()  # windows
            else:  # user did not save
                self.openAfterMaybeSave()  # finalize new

    def actionDropSlot(self):
        """
        1. If document is untouched, proceed to open dialog.
        2. If document is dirty, call maybesave and continue if it succeeds.
        Equivalent to actionOpenSlot() for Drag and Drop Event.
        """
        if self.maybeSave() is False:
            return  # user canceled in maybe save
        else:  # user did not cancel
            if hasattr(self, "filesavedialog"):  # user did save
                if self.filesavedialog is not None:
                    self.filesavedialog.finished.connect(self.openDropAfterMaybeSave)
                else:
                    self.openDropAfterMaybeSave()  # windows
            else:  # user did not save
                self.openDropAfterMaybeSave()  # finalize new

    def actionCloseSlot(self):
        """This will trigger a Window closeEvent."""
        if util.isWindows():
            #print "close win"
            if self.win is not None:
                self.win.close()
            if not app().isInMaya():
                #print "exit app"
                import sys
                sys.exit(1)

    def actionSaveSlot(self):
        """SaveAs if necessary, otherwise overwrite existing file."""
        if self._hasNoAssociatedFile:
            self.saveFileDialog()
            return
        self.writeDocumentToFile()

    def actionSaveAsSlot(self):
        """Open a save file dialog so user can choose a name."""
        self.saveFileDialog()

    def actionSVGSlot(self):
        """docstring for actionSVGSlot"""
        fname = os.path.basename(str(self.filename()))
        if fname == None:
            directory = "."
        else:
            directory = QFileInfo(fname).path()

        fdialog = QFileDialog(
                    self.win,
                    "%s - Save As" % QApplication.applicationName(),
                    directory,
                    "%s (*.svg)" % QApplication.applicationName())
        fdialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        fdialog.setWindowFlags(Qt.WindowType.Sheet)
        fdialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.svgsavedialog = fdialog
        self.svgsavedialog.filesSelected.connect(self.saveSVGDialogCallback)
        fdialog.open()

    class DummyChild(QGraphicsItem):
        def boundingRect(self):
            return QRect(200, 200) # self.parentObject().boundingRect()
        def paint(self, painter, option, widget=None):
            pass

    def saveSVGDialogCallback(self, selected):
        if isinstance(selected, (list, tuple)):
            fname = selected[0]
        else:
            fname = selected
        if not fname or fname is None or os.path.isdir(fname):
            return False
        fname = str(fname)
        if not fname.lower().endswith(".svg"):
            fname += ".svg"
        if self.svgsavedialog != None:
            self.svgsavedialog.filesSelected.disconnect(self.saveSVGDialogCallback)
            del self.svgsavedialog  # prevents hang
            self.svgsavedialog = None

        generator = QSvgGenerator()
        generator.setFileName(fname)
        generator.setSize(QSize(200, 200))
        generator.setViewBox(QRect(0, 0, 2000, 2000))
        painter = QPainter()

        # Render through scene
        # painter.begin(generator)
        # self.win.pathscene.render(painter)
        # painter.end()

        # Render item-by-item
        painter = QPainter()
        styleOption = QStyleOptionGraphicsItem()
        q = [self.win.pathroot]
        painter.begin(generator)
        while q:
            graphicsItem = q.pop()
            transform = graphicsItem.itemTransform(self.win.sliceroot)[0]
            painter.setTransform(transform)
            if graphicsItem.isVisible():
                graphicsItem.paint(painter, styleOption, None)
                q.extend(graphicsItem.childItems())
        painter.end()

    def actionExportStaplesSlot(self):
        """
        Triggered by clicking Export Staples button. Opens a file dialog to
        determine where the staples should be saved. The callback is
        exportStaplesCallback which collects the staple sequences and exports
        the file.
        """
        # Validate that no staple oligos are loops.
        part = self.activePart()
        stapLoopOlgs = part.getStapleLoopOligos()
        if stapLoopOlgs:
            from cadnano2.ui.dialogs.ui_warning import Ui_Warning
            dialog = QDialog()
            dialogWarning = Ui_Warning()
            dialog.setStyleSheet("QDialog { background-image: url(ui/dialogs/images/cadnano2-about.png); background-repeat: none; }")
            dialogWarning.setupUi(dialog, name="Warning-Circular")

            locs = ", ".join([o.locString() for o in stapLoopOlgs])
            msg = "Part contains staple loop(s) at %s.\n\nUse the break tool to introduce 5' & 3' ends before exporting. Loops have been colored red; use undo to revert." % locs
            dialogWarning.title.setText("Staple validation failed")
            dialogWarning.message.setText(msg)
            for o in stapLoopOlgs:
                o.applyColor(styles.stapColors[0].name())
            dialog.exec()
            return

        # Proceed with staple export.
        fname = self.filename()
        if fname == None:
            directory = "."
        else:
            directory = QFileInfo(fname).path()
        if util.isWindows():  # required for native looking file window
            fname = QFileDialog.getSaveFileName(
                            self.win,
                            "%s - Export As" % QApplication.applicationName(),
                            directory,
                            "(*.csv)")
            self.saveStaplesDialog = None
            self.exportStaplesCallback(fname)
        else:  # access through non-blocking callback
            fdialog = QFileDialog(
                            self.win,
                            "%s - Export As" % QApplication.applicationName(),
                            directory,
                            "(*.csv)")
            fdialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            fdialog.setWindowFlags(Qt.WindowType.Sheet)
            fdialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.saveStaplesDialog = fdialog
            self.saveStaplesDialog.filesSelected.connect(self.exportStaplesCallback)
            fdialog.open()
    # end def

    def actionPrefsSlot(self):
        app().prefsClicked()

    def actionAutostapleSlot(self):
        part = self.activePart()
        if part:
            self.win.pathGraphicsView.setViewportUpdateOn(False)
            part.autoStaple()
            self.win.pathGraphicsView.setViewportUpdateOn(True)

    def actionModifySlot(self):
        """
        Notifies that part root items that parts should respond to modifier
        selection signals.
        """
        # uncomment for debugging
        # isChecked = self.win.actionModify.isChecked()
        # self.win.pathroot.setModifyState(isChecked)
        # self.win.sliceroot.setModifyState(isChecked)
        if app().isInMaya():
            isChecked = self.win.actionModify.isChecked()
            self.win.pathroot.setModifyState(isChecked)
            self.win.sliceroot.setModifyState(isChecked)
            self.win.solidroot.setModifyState(isChecked)

    def actionAddHoneycombPartSlot(self):
        """docstring for actionAddHoneycombPartSlot"""
        part = self._document.addHoneycombPart()
        self.setActivePart(part)

    def actionAddSquarePartSlot(self):
        """docstring for actionAddSquarePartSlot"""
        part = self._document.addSquarePart()
        self.setActivePart(part)

    def actionRenumberSlot(self):
        coordList = self.win.pathroot.getSelectedPartOrderedVHList()
        part = self.activePart()
        part.renumber(coordList)
    # end def

    ### ACCESSORS ###
    def document(self):
        return self._document

    def window(self):
        return self.win

    def setDocument(self, doc):
        """
        Sets the controller's document, and informs the document that
        this is its controller.
        """
        self._document = doc
        doc.setController(self)

    def activePart(self):
        if self._activePart == None:
            self._activePart = self._document.selectedPart()
        return self._activePart

    def setActivePart(self, part):
        self._activePart = part

    def undoStack(self):
        return self._document.undoStack()

    ### PRIVATE SUPPORT METHODS ###
    def newDocument(self, doc=None, fname=None):
        """Creates a new Document, reusing the DocumentController."""
        self._document.resetViews()
        self._document.removeAllParts()  # clear out old parts
        self._document.undoStack().clear()  # reset undostack
        self._filename = fname if fname else "untitled.json"
        self._hasNoAssociatedFile = fname == None
        self._activePart = None
        self.win.setWindowTitle(self.documentTitle() + '[*]')

    def saveFileDialog(self):
        fname = self.filename()
        if fname == None:
            directory = "."
        else:
            directory = QFileInfo(fname).path()
        if util.isWindows():  # required for native looking file window
            fname = QFileDialog.getSaveFileName(
                            self.win,
                            "%s - Save As" % QApplication.applicationName(),
                            directory,
                            "%s (*.json)" % QApplication.applicationName())
            self.writeDocumentToFile(fname)
        else:  # access through non-blocking callback
            fdialog = QFileDialog(
                            self.win,
                            "%s - Save As" % QApplication.applicationName(),
                            directory,
                            "%s (*.json)" % QApplication.applicationName())
            fdialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            fdialog.setWindowFlags(Qt.WindowType.Sheet)
            fdialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.filesavedialog = fdialog
            self.filesavedialog.filesSelected.connect(
                                                self.saveFileDialogCallback)
            fdialog.open()
    # end def

    def _readSettings(self):
        self.settings.beginGroup("FileSystem")
        self._fileOpenPath = self.settings.value("openpath", QDir().homePath())
        self.settings.endGroup()

    def _writeFileOpenPath(self, path):
        """docstring for _writePath"""
        self._fileOpenPath = path
        self.settings.beginGroup("FileSystem")
        self.settings.setValue("openpath", path)
        self.settings.endGroup()

    ### SLOT CALLBACKS ###
    def actionNewSlotCallback(self):
        """
        Gets called on completion of filesavedialog after newClicked's
        maybeSave. Removes the dialog if necessary, but it was probably
        already removed by saveFileDialogCallback.
        """
        if self.filesavedialog != None:
            self.filesavedialog.finished.disconnect(self.actionNewSlotCallback)
            del self.filesavedialog  # prevents hang (?)
            self.filesavedialog = None
        self.newDocument()

    def exportStaplesCallback(self, selected):
        """Export all staple sequences to selected CSV file.

        Args:
            selected (Tuple, List or str): if a List or Tuple, the filename
            should be the first element
        """
        if isinstance(selected, (list, tuple)):
            fname = selected[0]
        else:
            fname = selected
        # Return if fname is '', None, or a directory path
        if not fname or fname is None or os.path.isdir(fname):
            return False
        # if not fname.lower().endswith(".txt"):
        #     fname += ".txt"
        if self.saveStaplesDialog is not None:
            self.saveStaplesDialog.filesSelected.disconnect(self.exportStaplesCallback)
            # manual garbage collection to prevent hang (in osx)
            del self.saveStaplesDialog
            self.saveStaplesDialog = None
        # write the file
        ap = self.activePart()
        if ap is not None:
            output = ap.getStapleSequences()
            with open(fname, 'w') as f:
                f.write(output)
    # end def

    def newClickedCallback(self):
        """
        Gets called on completion of filesavedialog after newClicked's
        maybeSave. Removes the dialog if necessary, but it was probably
        already removed by saveFileDialogCallback.
        """

        if self.filesavedialog != None:
            self.filesavedialog.finished.disconnect(self.newClickedCallback)
            del self.filesavedialog  # prevents hang (?)
            self.filesavedialog = None
        self.newDocument()

    def openAfterMaybeSaveCallback(self, selected):
        """
        Receives file selection info from the dialog created by
        openAfterMaybeSave, following user input.

        Extracts the file name and passes it to the decode method, which
        returns a new document doc, which is then set as the open document
        by newDocument. Calls finalizeImport and disconnects dialog signaling.
        """
        if isinstance(selected, (list, tuple)):
            fname = selected[0]
        else:
            fname = selected
        if fname is None or fname == '' or os.path.isdir(fname):
            return False
        if not os.path.exists(fname):
            return False
        self._writeFileOpenPath(os.path.dirname(fname))
        self.newDocument(fname=fname)

        with io.open(fname, 'r', encoding='utf-8') as fd:
            decode(self._document, fd.read())

        if hasattr(self, "filesavedialog"):  # user did save
            if self.fileopendialog is not None:
                self.fileopendialog.filesSelected.disconnect(self.openAfterMaybeSaveCallback)
            # manual garbage collection to prevent hang (in osx)
            del self.fileopendialog
            self.fileopendialog = None

    def saveFileDialogCallback(self, selected):
        """If the user chose to save, write to that file."""
        if isinstance(selected, (list, tuple)):
            fname = selected[0]
        else:
            fname = selected
        if fname is None or os.path.isdir(fname):
            return False
        if not fname.lower().endswith(".json"):
            fname += ".json"
        if self.filesavedialog is not None:
            self.filesavedialog.filesSelected.disconnect(self.saveFileDialogCallback)
            del self.filesavedialog  # prevents hang
            self.filesavedialog = None
        self.writeDocumentToFile(fname)
        self._writeFileOpenPath(os.path.dirname(fname))

    ### EVENT HANDLERS ###
    def windowCloseEventHandler(self, event):
        """Intercept close events when user attempts to close the window."""
        if self.maybeSave():
            event.accept()
            if app().isInMaya():
                self.windock.setVisible(False)
                del self.windock
                self.windock = None
            the_app = app()
            self.destroyDC()
            if the_app.documentControllers:
                the_app.destroyApp()
        else:
            event.ignore()
        self.actionCloseSlot()

    ### FILE INPUT ##
    def documentTitle(self):
        fname = os.path.basename(str(self.filename()))
        if not self.undoStack().isClean():
            fname += '[*]'
        return fname

    def filename(self):
        return self._filename

    def setFilename(self, proposedFName):
        if self._filename == proposedFName:
            return True
        self._filename = proposedFName
        self._hasNoAssociatedFile = False
        self.win.setWindowTitle(self.documentTitle())
        return True

    def openDropAfterMaybeSave(self):
        """
        This is the method that initiates file opening after a drag and Drop event.
        It is called by actionDropSlot.
        """
        fname = self.win._dropped_file
        if fname.endswith(".json"):
            self.openAfterMaybeSaveCallback(fname)
        else:
            print(f"Ignoring dropped file {fname}. Use a cadnano.json file.")

    def openAfterMaybeSave(self):
        """
        This is the method that initiates file opening. It is called by
        actionOpenSlot to spawn a QFileDialog and connect it to a callback
        method.
        """
        path = self._fileOpenPath
        if util.isWindows():  # required for native looking file window#"/",
            fname = QFileDialog.getOpenFileName(
                        None,
                        "Open Document", path,
                        "cadnano1 / cadnano2 Files (*.nno *.json *.cadnano)")
            self.filesavedialog = None
            self.openAfterMaybeSaveCallback(fname)
        else:  # access through non-blocking callback
            fdialog = QFileDialog(
                        self.win,
                        "Open Document",
                        path,
                        "cadnano1 / cadnano2 Files (*.nno *.json *.cadnano)")
            fdialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            fdialog.setWindowFlags(Qt.WindowType.Sheet)
            fdialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.fileopendialog = fdialog
            self.fileopendialog.filesSelected.connect(self.openAfterMaybeSaveCallback)
            fdialog.open()
    # end def

    ### FILE OUTPUT ###
    def maybeSave(self):
        """Save on quit, check if document changes have occured."""
        if app().dontAskAndJustDiscardUnsavedChanges:
            return True
        if not self.undoStack().isClean():    # document dirty?
            savebox = QMessageBox(QMessageBox.Icon.Question,   "Application",
                "The document has been modified.\nDo you want to save your changes?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                self.win,
                Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint | Qt.WindowType.Sheet)
            savebox.setWindowModality(Qt.WindowModality.WindowModal)
            save = savebox.button(QMessageBox.StandardButton.Save)
            discard = savebox.button(QMessageBox.StandardButton.Discard)
            cancel = savebox.button(QMessageBox.StandardButton.Cancel)
            save.setShortcut("Ctrl+S")
            discard.setShortcut(QKeySequence("D,Ctrl+D"))
            cancel.setShortcut(QKeySequence("C,Ctrl+C,.,Ctrl+."))
            ret = savebox.exec()
            del savebox  # manual garbage collection to prevent hang (in osx)
            if ret == QMessageBox.StandardButton.Save:
                return self.actionSaveAsSlot()
            elif ret == QMessageBox.StandardButton.Cancel:
                return False
        return True

    def writeDocumentToFile(self, filename=None):
        helixOrderList = self.win.pathroot.getSelectedPartOrderedVHList()

        if helixOrderList == None:  # Do not attempt to save an empty design
            print("Cannot save empty document.")
            return False

        if filename == None:
            assert(not self._hasNoAssociatedFile)
            filename = self.filename()
        try:
            if util.isWindows() and isinstance(filename, (list,tuple)):
                filename = filename[0]
            with open(filename, 'w') as f:
                encode(self._document, helixOrderList, f)
        except IOError:
            flags = Qt.WindowType.Dialog | Qt.MSWindowsFixedSizeDialogHint | Qt.WindowType.Sheet
            errorbox = QMessageBox(QMessageBox.Critical,
                                   "cadnano",
                                   "Could not write to '%s'." % filename,
                                   QMessageBox.Ok,
                                   self.win,
                                   flags)
            errorbox.setWindowModality(Qt.WindowModality.WindowModal)
            errorbox.open()
            return False
        self.undoStack().setClean()
        self.setFilename(filename)
        return True

    def actionCadnanoWebsiteSlot(self):
        import webbrowser
        webbrowser.open("http://cadnano.org/")

    def actionFeedbackSlot(self):
        import webbrowser
        webbrowser.open("http://cadnano.org/feedback")
