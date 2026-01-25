"""
agentmethods.py

Methods layer for agent-controlled document modifications.
Provides constrained, atomic operations on cadnano documents.
"""

from cadnano2.model.enum import StrandType


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

    # ==================== GEOMETRY & INTROSPECTION ====================

    def getActivePartInfo(self):
        """Return information about the active part."""
        part = self.activePart
        if part is None:
            return "No active part. Create a new Honeycomb or Square part first."
        vhs = part.getVirtualHelices()
        return {
            'type': part.__class__.__name__,
            'virtualHelixCount': len(vhs),
            'helixNumbers': [vh.number() for vh in vhs],
            'maxBaseIdx': part.maxBaseIdx(),
            'step': part._step
        }

    def getHelixInfo(self, helix_num):
        """
        Get detailed information about a specific helix.

        Args:
            helix_num (int): The virtual helix number

        Returns:
            dict or str: Helix info or error message
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        row, col = vh.coord()
        scafSS = vh.scaffoldStrandSet()
        stapSS = vh.stapleStrandSet()

        scaf_strands = []
        for strand in scafSS:
            lo, hi = strand.idxs()
            scaf_strands.append({'low': lo, 'high': hi})

        stap_strands = []
        for strand in stapSS:
            lo, hi = strand.idxs()
            stap_strands.append({'low': lo, 'high': hi})

        return {
            'helix_num': helix_num,
            'row': row,
            'col': col,
            'parity': 'even' if part.isEvenParity(row, col) else 'odd',
            'scaffold_strands': scaf_strands,
            'staple_strands': stap_strands
        }

    def getHoneycombPositions(self, num_helices):
        """
        Get (row, col) positions for a honeycomb bundle.

        Args:
            num_helices (int): Number of helices (2, 6, 7, 19, etc.)

        Returns:
            list: List of (row, col) tuples
        """
        # Standard honeycomb bundle positions centered around (20, 20)
        # These form hexagonal patterns
        positions = {
            1: [(20, 20)],
            2: [(20, 20), (20, 21)],
            3: [(20, 20), (20, 21), (21, 20)],
            4: [(20, 20), (20, 21), (21, 20), (21, 21)],
            6: [
                (20, 20), (20, 21),  # top row
                (21, 20), (21, 21),  # middle row
                (22, 20), (22, 21)   # bottom row
            ],
            7: [
                (20, 21),            # top
                (21, 20), (21, 21), (21, 22),  # middle row
                (22, 20), (22, 21), (22, 22)   # bottom row
            ],
            19: [
                # 19-helix bundle (3 rows of increasing size)
                (19, 20), (19, 21), (19, 22),
                (20, 19), (20, 20), (20, 21), (20, 22), (20, 23),
                (21, 19), (21, 20), (21, 21), (21, 22), (21, 23),
                (22, 20), (22, 21), (22, 22), (22, 23),
                (23, 21), (23, 22)
            ]
        }

        if num_helices in positions:
            return f"Positions for {num_helices}-helix bundle: {positions[num_helices]}"

        # For arbitrary numbers, generate a simple rectangular arrangement
        cols = min(num_helices, 3)
        rows = (num_helices + cols - 1) // cols
        result = []
        count = 0
        for r in range(rows):
            for c in range(cols):
                if count >= num_helices:
                    break
                result.append((20 + r, 20 + c))
                count += 1
        return f"Positions for {num_helices}-helix bundle: {result}"

    def listHelices(self):
        """List all helices with their numbers and positions."""
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vhs = part.getVirtualHelices()
        if not vhs:
            return "No helices in design"

        result = []
        for vh in vhs:
            row, col = vh.coord()
            parity = 'even' if part.isEvenParity(row, col) else 'odd'
            result.append({
                'num': vh.number(),
                'row': row,
                'col': col,
                'parity': parity
            })
        return f"Helices: {result}"

    def getPotentialCrossovers(self, helix_num, strand_type):
        """
        Get potential crossover positions for a helix.

        Args:
            helix_num (int): The virtual helix number
            strand_type (str): "scaffold" or "staple"

        Returns:
            list: Potential crossover positions
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        st = StrandType.Scaffold if strand_type.lower() == "scaffold" else StrandType.Staple
        crossovers = part.potentialCrossoverList(vh)

        # Filter by strand type and format results
        result = []
        for neighborVh, idx, sType, isLowIdx in crossovers:
            if sType == st and neighborVh is not None:
                result.append({
                    'idx': idx,
                    'neighbor_helix': neighborVh.number(),
                    'is_low_idx': isLowIdx
                })

        return f"Potential {strand_type} crossovers for helix {helix_num}: {result}"

    # ==================== HELIX MANAGEMENT ====================

    def createHelix(self, row, col):
        """
        Create a virtual helix at the specified grid position.

        Args:
            row (int): Row in the lattice grid
            col (int): Column in the lattice grid

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part. Create a Honeycomb or Square part first."

        # Check if helix already exists at this position
        existing = part.virtualHelixAtCoord((row, col))
        if existing is not None:
            return f"Error: Helix already exists at ({row}, {col}) with number {existing.number()}"

        try:
            part.createVirtualHelix(row, col, useUndoStack=True)
            vh = part.virtualHelixAtCoord((row, col))
            if vh:
                return f"Created helix {vh.number()} at ({row}, {col})"
            return f"Created helix at ({row}, {col})"
        except Exception as e:
            return f"Error creating helix: {e}"

    # ==================== STRAND MANAGEMENT ====================

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

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Virtual helix {helix_num} not found"

        scafStrandSet = vh.scaffoldStrandSet()
        end_idx = start_idx + length - 1

        maxBaseIdx = part.maxBaseIdx()
        if start_idx < 0 or end_idx > maxBaseIdx:
            return f"Error: Index out of range. Valid range: 0-{maxBaseIdx}"

        if start_idx > end_idx:
            return f"Error: Invalid range: start_idx ({start_idx}) > end_idx ({end_idx})"

        boundsLow, boundsHigh = scafStrandSet.getBoundsOfEmptyRegionContaining(start_idx)
        if boundsLow is None or boundsHigh is None:
            return f"Error: Position {start_idx} is not in an empty region"

        if end_idx > boundsHigh:
            return f"Error: Strand would overlap existing strand. Empty region: {boundsLow}-{boundsHigh}"

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

    # ==================== CROSSOVER MANAGEMENT ====================

    def createCrossover(self, helix1, idx1, helix2, idx2, strand_type):
        """
        Create a crossover between two helices.

        Args:
            helix1 (int): First helix number
            idx1 (int): Index on first helix
            helix2 (int): Second helix number
            idx2 (int): Index on second helix
            strand_type (str): "scaffold" or "staple"

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh1 = part.virtualHelix(helix1)
        vh2 = part.virtualHelix(helix2)

        if vh1 is None:
            return f"Error: Helix {helix1} not found"
        if vh2 is None:
            return f"Error: Helix {helix2} not found"

        if strand_type.lower() == "scaffold":
            ss1 = vh1.scaffoldStrandSet()
            ss2 = vh2.scaffoldStrandSet()
        else:
            ss1 = vh1.stapleStrandSet()
            ss2 = vh2.stapleStrandSet()

        strand1 = ss1.getStrand(idx1)
        strand2 = ss2.getStrand(idx2)

        if strand1 is None:
            return f"Error: No {strand_type} strand at helix {helix1} index {idx1}"
        if strand2 is None:
            return f"Error: No {strand_type} strand at helix {helix2} index {idx2}"

        try:
            part.createXover(strand1, idx1, strand2, idx2, useUndoStack=True)
            return f"Created {strand_type} crossover: helix {helix1}[{idx1}] <-> helix {helix2}[{idx2}]"
        except Exception as e:
            return f"Error creating crossover: {e}"

    def findCrossoversWithSpacing(self, strand_type, min_spacing=21):
        """
        Find all potential crossovers that satisfy minimum spacing.

        Args:
            strand_type (str): "scaffold" or "staple"
            min_spacing (int): Minimum base pairs between crossovers

        Returns:
            str: List of valid crossover positions
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        st = StrandType.Scaffold if strand_type.lower() == "scaffold" else StrandType.Staple
        all_crossovers = []

        for vh in part.getVirtualHelices():
            crossovers = part.potentialCrossoverList(vh)
            for neighborVh, idx, sType, isLowIdx in crossovers:
                if sType == st and neighborVh is not None:
                    # Only add if from lower helix number to avoid duplicates
                    if vh.number() < neighborVh.number():
                        all_crossovers.append({
                            'helix1': vh.number(),
                            'helix2': neighborVh.number(),
                            'idx': idx,
                            'is_low_idx': isLowIdx
                        })

        # Sort by index and filter by spacing
        all_crossovers.sort(key=lambda x: (x['helix1'], x['helix2'], x['idx']))

        # Group by helix pair
        from collections import defaultdict
        by_pair = defaultdict(list)
        for xo in all_crossovers:
            key = (xo['helix1'], xo['helix2'])
            by_pair[key].append(xo)

        # Filter each pair by spacing
        valid_crossovers = []
        for pair, xos in by_pair.items():
            last_idx = -min_spacing  # Allow first crossover
            for xo in xos:
                if xo['idx'] - last_idx >= min_spacing:
                    valid_crossovers.append(xo)
                    last_idx = xo['idx']

        return f"Valid {strand_type} crossovers with {min_spacing}bp spacing: {valid_crossovers}"

    # ==================== INSERTIONS & DELETIONS ====================

    def addInsertion(self, helix_num, idx, length):
        """
        Add an insertion or deletion at the specified position.

        Args:
            helix_num (int): The virtual helix number
            idx (int): Base index
            length (int): Positive for insertion, -1 for deletion

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        # Try scaffold first, then staple
        scafSS = vh.scaffoldStrandSet()
        stapSS = vh.stapleStrandSet()

        strand = scafSS.getStrand(idx)
        if strand is None:
            strand = stapSS.getStrand(idx)

        if strand is None:
            return f"Error: No strand at helix {helix_num} index {idx}"

        try:
            strand.addInsertion(idx, length, useUndoStack=True)
            if length > 0:
                return f"Added {length}-base insertion at helix {helix_num} index {idx}"
            else:
                return f"Added deletion at helix {helix_num} index {idx}"
        except Exception as e:
            return f"Error adding insertion: {e}"

    def removeInsertion(self, helix_num, idx):
        """
        Remove an insertion or deletion at the specified position.

        Args:
            helix_num (int): The virtual helix number
            idx (int): Base index

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        scafSS = vh.scaffoldStrandSet()
        stapSS = vh.stapleStrandSet()

        strand = scafSS.getStrand(idx)
        if strand is None:
            strand = stapSS.getStrand(idx)

        if strand is None:
            return f"Error: No strand at helix {helix_num} index {idx}"

        if not strand.hasInsertionAt(idx):
            return f"Error: No insertion at helix {helix_num} index {idx}"

        try:
            strand.removeInsertion(idx, useUndoStack=True)
            return f"Removed insertion at helix {helix_num} index {idx}"
        except Exception as e:
            return f"Error removing insertion: {e}"

    # ==================== CONVENIENCE METHODS ====================

    def createFullLengthStrands(self, helix_num, strand_type, start_idx=0, end_idx=None):
        """
        Create a full-length strand on a helix.

        Args:
            helix_num (int): The virtual helix number
            strand_type (str): "scaffold" or "staple"
            start_idx (int): Starting index (default 0)
            end_idx (int): Ending index (default maxBaseIdx)

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        if end_idx is None:
            end_idx = part.maxBaseIdx()

        length = end_idx - start_idx + 1

        if strand_type.lower() == "scaffold":
            return self.createScaffoldStrand(helix_num, start_idx, length)
        else:
            return self.createStapleStrand(helix_num, start_idx, length)
