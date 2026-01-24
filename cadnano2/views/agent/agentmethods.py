"""
agentmethods.py

Methods layer for agent-controlled document modifications.
Provides constrained, atomic operations on cadnano documents.
"""


class AgentMethods:
    """
    Provides methods for the agent to interact with cadnano documents.

    This layer ensures that the agent can only make controlled,
    reversible modifications to the document through well-defined methods.
    """

    def __init__(self, documentController):
        """
        Initialize with a reference to the document controller.

        Args:
            documentController: The DocumentController instance
        """
        self._documentController = documentController

    @property
    def document(self):
        """Get the current document."""
        return self._documentController.document()

    @property
    def activePart(self):
        """Get the active part, if any."""
        return self._documentController.activePart()

    # Document introspection methods

    def getPartCount(self):
        """Return the number of parts in the document."""
        return len(self.document.parts())

    def getPartInfo(self):
        """Return information about all parts in the document."""
        parts = self.document.parts()
        info = []
        for part in parts:
            info.append({
                'type': part.__class__.__name__,
                'virtualHelixCount': len(part.getVirtualHelices()) if hasattr(part, 'getVirtualHelices') else 0
            })
        return info

    def getActivePartInfo(self):
        """Return information about the active part."""
        part = self.activePart
        if part is None:
            return None
        return {
            'type': part.__class__.__name__,
            'virtualHelixCount': len(part.getVirtualHelices()) if hasattr(part, 'getVirtualHelices') else 0
        }

    # Placeholder methods for future functionality

    def addCrossover(self, vh1, idx1, vh2, idx2, isScaffold=True):
        """
        Add a crossover between two virtual helices.

        Args:
            vh1: First virtual helix number
            idx1: Index on first virtual helix
            vh2: Second virtual helix number
            idx2: Index on second virtual helix
            isScaffold: True for scaffold, False for staple

        Returns:
            bool: Success status

        Note: This is a placeholder - implementation pending.
        """
        # TODO: Implement crossover addition
        return False

    def addRegularCrossovers(self, startVh, endVh, startIdx, endIdx, spacing, isScaffold=True):
        """
        Add regularly spaced crossovers between virtual helices.

        Args:
            startVh: Starting virtual helix number
            endVh: Ending virtual helix number
            startIdx: Starting index
            endIdx: Ending index
            spacing: Spacing between crossovers
            isScaffold: True for scaffold, False for staple

        Returns:
            int: Number of crossovers added

        Note: This is a placeholder - implementation pending.
        """
        # TODO: Implement regular crossover addition
        return 0

    def copySelection(self):
        """
        Copy the current selection to a buffer.

        Returns:
            bool: Success status

        Note: This is a placeholder - implementation pending.
        """
        # TODO: Implement copy functionality
        return False

    def pasteSelection(self, targetVh, targetIdx):
        """
        Paste the buffered selection at a target location.

        Args:
            targetVh: Target virtual helix number
            targetIdx: Target index

        Returns:
            bool: Success status

        Note: This is a placeholder - implementation pending.
        """
        # TODO: Implement paste functionality
        return False
