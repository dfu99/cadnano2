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

    def executeMethod(self, methodName, params):
        """
        Execute a method by name with given parameters.

        Args:
            methodName (str): Name of the method to call
            params (dict): Parameters to pass to the method

        Returns:
            tuple: (success: bool, message: str)
        """
        method = getattr(self, methodName, None)
        if method is None:
            return False, f"Unknown method: {methodName}"

        try:
            result = method(**params)
            return True, result
        except TypeError as e:
            return False, f"Invalid parameters: {e}"
        except Exception as e:
            return False, f"Error executing {methodName}: {e}"

    # Document introspection methods

    def getPartCount(self):
        """Return the number of parts in the document."""
        return len(self.document.parts())

    def getPartInfo(self):
        """Return information about all parts in the document."""
        parts = self.document.parts()
        info = []
        for part in parts:
            vhs = part.getVirtualHelices()
            info.append({
                'type': part.__class__.__name__,
                'virtualHelixCount': len(vhs),
                'helixNumbers': [vh.number() for vh in vhs]
            })
        return info

    def getActivePartInfo(self):
        """Return information about the active part."""
        part = self.activePart
        if part is None:
            return None
        vhs = part.getVirtualHelices()
        return {
            'type': part.__class__.__name__,
            'virtualHelixCount': len(vhs),
            'helixNumbers': [vh.number() for vh in vhs],
            'maxBaseIdx': part.maxBaseIdx()
        }

    # Strand creation methods

    def createScaffoldStrand(self, helix_num, start_idx, length):
        """
        Create a scaffold strand on the specified helix.

        Args:
            helix_num (int): The virtual helix number
            start_idx (int): Starting base index
            length (int): Length of the strand in bases

        Returns:
            str: Success message or error description
        """
        part = self.activePart
        if part is None:
            return "Error: No active part in document"

        # Get the virtual helix by number
        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Virtual helix {helix_num} not found"

        # Get the scaffold strand set
        scafStrandSet = vh.scaffoldStrandSet()

        # Calculate end index
        end_idx = start_idx + length - 1

        # Validate indices
        maxBaseIdx = part.maxBaseIdx()
        if start_idx < 0 or end_idx > maxBaseIdx:
            return f"Error: Index out of range. Valid range: 0-{maxBaseIdx}"

        if start_idx > end_idx:
            return f"Error: Invalid range: start_idx ({start_idx}) > end_idx ({end_idx})"

        # Check if the region is empty
        boundsLow, boundsHigh = scafStrandSet.getBoundsOfEmptyRegionContaining(start_idx)
        if boundsLow is None or boundsHigh is None:
            return f"Error: Position {start_idx} is not in an empty region"

        if end_idx > boundsHigh:
            return f"Error: Strand would overlap existing strand. Empty region: {boundsLow}-{boundsHigh}"

        # Create the strand
        result = scafStrandSet.createStrand(start_idx, end_idx, useUndoStack=True)

        if result >= 0:
            return f"Created scaffold strand on helix {helix_num} from index {start_idx} to {end_idx}"
        else:
            return f"Error: Could not create strand (region may not be empty)"

    def createStapleStrand(self, helix_num, start_idx, length):
        """
        Create a staple strand on the specified helix.

        Args:
            helix_num (int): The virtual helix number
            start_idx (int): Starting base index
            length (int): Length of the strand in bases

        Returns:
            str: Success message or error description
        """
        part = self.activePart
        if part is None:
            return "Error: No active part in document"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Virtual helix {helix_num} not found"

        stapStrandSet = vh.stapleStrandSet()
        end_idx = start_idx + length - 1

        maxBaseIdx = part.maxBaseIdx()
        if start_idx < 0 or end_idx > maxBaseIdx:
            return f"Error: Index out of range. Valid range: 0-{maxBaseIdx}"

        if start_idx > end_idx:
            return f"Error: Invalid range: start_idx ({start_idx}) > end_idx ({end_idx})"

        boundsLow, boundsHigh = stapStrandSet.getBoundsOfEmptyRegionContaining(start_idx)
        if boundsLow is None or boundsHigh is None:
            return f"Error: Position {start_idx} is not in an empty region"

        if end_idx > boundsHigh:
            return f"Error: Strand would overlap existing strand. Empty region: {boundsLow}-{boundsHigh}"

        result = stapStrandSet.createStrand(start_idx, end_idx, useUndoStack=True)

        if result >= 0:
            return f"Created staple strand on helix {helix_num} from index {start_idx} to {end_idx}"
        else:
            return f"Error: Could not create strand (region may not be empty)"

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
            str: Success message or error description

        Note: This is a placeholder - implementation pending.
        """
        return "Error: addCrossover not yet implemented"

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
            str: Success message or error description

        Note: This is a placeholder - implementation pending.
        """
        return "Error: addRegularCrossovers not yet implemented"
