"""
trajectorylogger.py

Trajectory logging for RLVR training data collection.
Captures agent sessions including actions, results, and rewards.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import cadnano2.util as util
util.qtWrapImport('QtCore', globals(), ['QObject', 'pyqtSignal'])


class TrajectoryLogger(QObject):
    """
    Logs agent trajectories for RLVR training.

    A trajectory consists of:
    - Task: The user's original request
    - Actions: List of method calls with parameters
    - Results: Outcomes of each action
    - Reward: Final verification score
    - Metadata: Timestamps, model info, etc.
    """

    trajectoryCompleted = pyqtSignal(dict)  # Emitted when a trajectory is saved

    def __init__(self, save_dir=None, parent=None):
        super().__init__(parent)

        # Default save directory
        if save_dir is None:
            home = Path.home()
            save_dir = home / ".cadnano2" / "trajectories"

        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)

        # Current trajectory being recorded
        self._current = None
        self._is_recording = False

    def startTrajectory(self, task, model=None, mode="edit"):
        """
        Start recording a new trajectory.

        Args:
            task (str): The user's task/prompt
            model (str): The model being used
            mode (str): "edit" or "developer"
        """
        self._current = {
            "id": self._generateId(),
            "timestamp_start": datetime.now().isoformat(),
            "timestamp_end": None,
            "task": task,
            "model": model,
            "mode": mode,
            "actions": [],
            "conversation": [],
            "final_score": None,
            "final_valid": None,
            "final_metrics": {},
            "success": None,
            "error": None
        }
        self._is_recording = True

    def logAction(self, method_name, params, result, success, validation_msg=None):
        """
        Log a method call and its result.

        Args:
            method_name (str): Name of the method called
            params (dict): Parameters passed to the method
            result (str): Result message from execution
            success (bool): Whether the action succeeded
            validation_msg (str): Optional validation message
        """
        if not self._is_recording or self._current is None:
            return

        action = {
            "timestamp": datetime.now().isoformat(),
            "method": method_name,
            "params": params,
            "result": result,
            "success": success,
            "validation_message": validation_msg
        }
        self._current["actions"].append(action)

    def logConversation(self, role, content):
        """
        Log a conversation turn.

        Args:
            role (str): "user", "assistant", or "system"
            content (str): The message content
        """
        if not self._is_recording or self._current is None:
            return

        turn = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content[:1000]  # Truncate long messages
        }
        self._current["conversation"].append(turn)

    def logVerification(self, score, valid, metrics):
        """
        Log the final verification result.

        Args:
            score (float): Reward score (0-1)
            valid (bool): Whether the design is valid
            metrics (dict): Verification metrics
        """
        if not self._is_recording or self._current is None:
            return

        self._current["final_score"] = score
        self._current["final_valid"] = valid
        self._current["final_metrics"] = metrics

    def endTrajectory(self, success=True, error=None):
        """
        End the current trajectory and save it.

        Args:
            success (bool): Whether the task completed successfully
            error (str): Error message if failed

        Returns:
            dict: The completed trajectory
        """
        if not self._is_recording or self._current is None:
            return None

        self._current["timestamp_end"] = datetime.now().isoformat()
        self._current["success"] = success
        self._current["error"] = error

        # Calculate duration
        start = datetime.fromisoformat(self._current["timestamp_start"])
        end = datetime.fromisoformat(self._current["timestamp_end"])
        self._current["duration_seconds"] = (end - start).total_seconds()

        # Save trajectory
        trajectory = self._current
        self._saveTrajectory(trajectory)

        # Reset state
        self._current = None
        self._is_recording = False

        self.trajectoryCompleted.emit(trajectory)
        return trajectory

    def cancelTrajectory(self):
        """Cancel the current trajectory without saving."""
        self._current = None
        self._is_recording = False

    def isRecording(self):
        """Return whether a trajectory is being recorded."""
        return self._is_recording

    def getCurrentTrajectory(self):
        """Return the current trajectory being recorded."""
        return self._current

    def _generateId(self):
        """Generate a unique trajectory ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import random
        suffix = random.randint(1000, 9999)
        return f"traj_{timestamp}_{suffix}"

    def _saveTrajectory(self, trajectory):
        """Save a trajectory to disk."""
        # Determine filename based on score
        score = trajectory.get("final_score", 0) or 0
        if score >= 0.8:
            subdir = "success"
        elif score >= 0.5:
            subdir = "partial"
        else:
            subdir = "failed"

        save_path = self._save_dir / subdir
        save_path.mkdir(parents=True, exist_ok=True)

        filename = f"{trajectory['id']}.json"
        filepath = save_path / filename

        with open(filepath, 'w') as f:
            json.dump(trajectory, f, indent=2, default=str)

        print(f"Trajectory saved: {filepath}")

    def loadTrajectory(self, trajectory_id):
        """
        Load a trajectory by ID.

        Args:
            trajectory_id (str): The trajectory ID

        Returns:
            dict: The trajectory or None if not found
        """
        for subdir in ["success", "partial", "failed"]:
            filepath = self._save_dir / subdir / f"{trajectory_id}.json"
            if filepath.exists():
                with open(filepath) as f:
                    return json.load(f)
        return None

    def listTrajectories(self, category=None):
        """
        List all saved trajectories.

        Args:
            category (str): Optional filter: "success", "partial", or "failed"

        Returns:
            list: List of trajectory summaries
        """
        trajectories = []
        subdirs = [category] if category else ["success", "partial", "failed"]

        for subdir in subdirs:
            subpath = self._save_dir / subdir
            if not subpath.exists():
                continue

            for filepath in subpath.glob("*.json"):
                try:
                    with open(filepath) as f:
                        traj = json.load(f)
                        trajectories.append({
                            "id": traj.get("id"),
                            "task": traj.get("task", "")[:100],
                            "score": traj.get("final_score"),
                            "success": traj.get("success"),
                            "action_count": len(traj.get("actions", [])),
                            "duration": traj.get("duration_seconds"),
                            "category": subdir
                        })
                except Exception as e:
                    print(f"Error loading {filepath}: {e}")

        return sorted(trajectories, key=lambda x: x.get("id", ""), reverse=True)

    def getTrainingData(self, min_score=0.8):
        """
        Get trajectories suitable for training.

        Args:
            min_score (float): Minimum score threshold

        Returns:
            list: List of high-quality trajectories
        """
        training_data = []

        for subdir in ["success", "partial"]:
            subpath = self._save_dir / subdir
            if not subpath.exists():
                continue

            for filepath in subpath.glob("*.json"):
                try:
                    with open(filepath) as f:
                        traj = json.load(f)
                        score = traj.get("final_score", 0) or 0
                        if score >= min_score:
                            training_data.append(traj)
                except Exception:
                    pass

        return training_data

    def exportForVerlTool(self, output_path, min_score=0.8):
        """
        Export trajectories in VerlTool-compatible format.

        Args:
            output_path (str): Path to save the export
            min_score (float): Minimum score threshold

        Returns:
            int: Number of trajectories exported
        """
        trajectories = self.getTrainingData(min_score)

        # Convert to VerlTool format
        verl_data = []
        for traj in trajectories:
            verl_entry = {
                "prompt": traj.get("task", ""),
                "trajectory": [],
                "reward": traj.get("final_score", 0)
            }

            # Convert actions to tool calls
            for action in traj.get("actions", []):
                verl_entry["trajectory"].append({
                    "tool": action.get("method"),
                    "arguments": action.get("params", {}),
                    "result": action.get("result", ""),
                    "success": action.get("success", False)
                })

            verl_data.append(verl_entry)

        # Save
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(verl_data, f, indent=2)

        print(f"Exported {len(verl_data)} trajectories to {output_path}")
        return len(verl_data)

    def getStatistics(self):
        """
        Get statistics about collected trajectories.

        Returns:
            dict: Statistics summary
        """
        stats = {
            "total": 0,
            "success": 0,
            "partial": 0,
            "failed": 0,
            "avg_score": 0,
            "avg_actions": 0,
            "avg_duration": 0
        }

        all_scores = []
        all_actions = []
        all_durations = []

        for subdir in ["success", "partial", "failed"]:
            subpath = self._save_dir / subdir
            if not subpath.exists():
                continue

            count = len(list(subpath.glob("*.json")))
            stats[subdir] = count
            stats["total"] += count

            for filepath in subpath.glob("*.json"):
                try:
                    with open(filepath) as f:
                        traj = json.load(f)
                        if traj.get("final_score") is not None:
                            all_scores.append(traj["final_score"])
                        all_actions.append(len(traj.get("actions", [])))
                        if traj.get("duration_seconds"):
                            all_durations.append(traj["duration_seconds"])
                except Exception:
                    pass

        if all_scores:
            stats["avg_score"] = sum(all_scores) / len(all_scores)
        if all_actions:
            stats["avg_actions"] = sum(all_actions) / len(all_actions)
        if all_durations:
            stats["avg_duration"] = sum(all_durations) / len(all_durations)

        return stats

    def getReplayActions(self, trajectory_id):
        """
        Get the list of actions from a trajectory for replay.

        Args:
            trajectory_id (str): The trajectory ID

        Returns:
            list: List of (method_name, params) tuples, or None if not found
        """
        traj = self.loadTrajectory(trajectory_id)
        if traj is None:
            return None

        actions = []
        for action in traj.get("actions", []):
            method = action.get("method")
            params = action.get("params", {})
            if method:
                actions.append((method, params))

        return actions

    def getTrajectoryInfo(self, trajectory_id):
        """
        Get summary info about a trajectory.

        Args:
            trajectory_id (str): The trajectory ID

        Returns:
            dict: Trajectory summary or None if not found
        """
        traj = self.loadTrajectory(trajectory_id)
        if traj is None:
            return None

        return {
            "id": traj.get("id"),
            "task": traj.get("task"),
            "model": traj.get("model"),
            "action_count": len(traj.get("actions", [])),
            "final_score": traj.get("final_score"),
            "success": traj.get("success"),
            "duration": traj.get("duration_seconds")
        }
