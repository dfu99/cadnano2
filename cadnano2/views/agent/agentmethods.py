"""
agentmethods.py

Methods layer for agent-controlled document modifications.
Provides constrained, atomic operations on cadnano documents.
"""

from cadnano2.model.enum import StrandType
from cadnano2.model.parts.honeycombpart import Crossovers
from .agentverifier import DesignVerifier


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

    def getHelixDirection(self, helix_num):
        """
        Get strand direction and neighbor info for a helix.

        Returns parity, which strand is on top, the 5'->3' direction for
        scaffold and staple, and the neighbor helices by direction.

        Args:
            helix_num (int): The virtual helix number

        Returns:
            str: Direction and neighbor information
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        row, col = vh.coord()
        even = part.isEvenParity(row, col)
        scafSS = vh.scaffoldStrandSet()
        stapSS = vh.stapleStrandSet()

        neighbors = part.getVirtualHelixNeighbors(vh)
        neighbor_info = []
        for i, n in enumerate(neighbors):
            if n is not None:
                neighbor_info.append(f"p{i}=helix {n.number()}")
            else:
                neighbor_info.append(f"p{i}=empty")

        info = {
            'helix_num': helix_num,
            'row': row,
            'col': col,
            'parity': 'even' if even else 'odd',
            'scaffold_on_top': vh.scaffoldIsOnTop(),
            'scaffold_5to3': 'left-to-right (low→high idx)' if vh.isDrawn5to3(scafSS) else 'right-to-left (high→low idx)',
            'staple_5to3': 'left-to-right (low→high idx)' if vh.isDrawn5to3(stapSS) else 'right-to-left (high→low idx)',
            'neighbors': ', '.join(neighbor_info),
        }

        lines = [f"{k}: {v}" for k, v in info.items()]
        return '\n'.join(lines)

    def getHoneycombPositions(self, num_helices):
        """
        Get (row, col) positions for a standard honeycomb bundle.

        Use these positions directly with createHelicesWithStrands, or just
        pass num_helices to createHelicesWithStrands and skip this call.

        Args:
            num_helices (int): Number of helices (1, 2, 3, 4, 6, 7, 19, …)

        Returns:
            dict: positions list and a tip to use num_helices directly
        """
        if num_helices in self._HONEYCOMB_BUNDLE_POSITIONS:
            pos = self._HONEYCOMB_BUNDLE_POSITIONS[num_helices]
        else:
            # Fallback: pack into a compact 2-column grid
            pos = []
            for i in range(num_helices):
                row = 20 + i // 2
                col = 20 + (i % 2)
                pos.append((row, col))

        return {
            'num_helices': num_helices,
            'positions': pos,
            'tip': (
                f'Pass num_helices={num_helices} directly to createHelicesWithStrands '
                f'to skip this step.'
            )
        }

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

    # ==================== PART SIZE MANAGEMENT ====================

    def extendPartSize(self, min_length_needed):
        """
        Extend the part size to accommodate the desired strand length.
        Use this when strand creation fails due to index out of range.

        Args:
            min_length_needed (int): Minimum number of bases needed (e.g., 84 for 84bp strands)

        Returns:
            str: Success message with new range, or error
        """
        from math import ceil

        part = self.activePart
        if part is None:
            return "Error: No active part"

        current_max = part.maxBaseIdx()
        step = part.stepSize()

        # Need max index to be at least min_length_needed - 1 (since indices are 0-based)
        needed_max_idx = min_length_needed - 1

        if needed_max_idx <= current_max:
            return f"Part already has sufficient size. Current range: 0-{current_max}"

        # Calculate how much to extend (must be multiple of step size)
        delta_needed = needed_max_idx - current_max
        # Round up to next multiple of step size
        delta = int(ceil(delta_needed / step)) * step

        try:
            part.resizeVirtualHelices(0, delta, useUndoStack=True)
            new_max = part.maxBaseIdx()
            return f"Extended part size. New range: 0-{new_max} (added {delta} bases)"
        except Exception as e:
            return f"Error extending part: {e}"

    def getPartSize(self):
        """
        Get the current part size information.

        Returns:
            str: Part size info including valid index range
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        min_idx = part.minBaseIdx()
        max_idx = part.maxBaseIdx()
        step = part.stepSize()

        return f"Part size: indices {min_idx}-{max_idx} (step size: {step}bp). Max strand length: {max_idx - min_idx + 1}bp"

    # ==================== SELECTION MANAGEMENT ====================

    def getSelectedStrands(self):
        """
        Get information about currently selected strands in the GUI.

        Returns:
            str: List of selected strands with their endpoints, or message if none selected
        """
        doc = self.document
        if doc is None:
            return "Error: No document"

        selectionDict = doc.selectionDict()
        if not selectionDict:
            return "No strands currently selected. Use the GUI to select strands first."

        selected = []
        for strandSet, strandDict in selectionDict.items():
            for strand, endpoints in strandDict.items():
                vh = strand.virtualHelix()
                idxL, idxH = strand.idxs()
                strand_type = "scaffold" if strand.isScaffold() else "staple"
                # endpoints is (lowSelected, highSelected)
                low_sel, high_sel = endpoints
                selected.append({
                    'helix': vh.number(),
                    'type': strand_type,
                    'low_idx': idxL,
                    'high_idx': idxH,
                    'low_selected': low_sel,
                    'high_selected': high_sel,
                    'has_low_connection': strand.connectionLow() is not None,
                    'has_high_connection': strand.connectionHigh() is not None
                })

        if not selected:
            return "No strands currently selected."

        return f"Selected strands: {selected}"

    def moveSelection(self, delta):
        """
        Move selected strand endpoints by delta base pairs.
        This maintains crossover connections through snap-to behavior.

        Args:
            delta (int): Number of base pairs to move (positive = right, negative = left)

        Returns:
            str: Success message or error
        """
        doc = self.document
        if doc is None:
            return "Error: No document"

        selectionDict = doc.selectionDict()
        if not selectionDict:
            return "Error: No strands selected. Select strands in the GUI first."

        try:
            doc.resizeSelection(delta, useUndoStack=True)
            return f"Moved selection by {delta} base pairs"
        except Exception as e:
            return f"Error moving selection: {e}"

    def clearSelection(self):
        """
        Clear all strand selections.

        Goes through the view's SelectionItemGroup to properly remove
        items from the graphics group, hide the selection box, and
        update both model and view state.

        Returns:
            str: Success message
        """
        doc = self.document
        if doc is None:
            return "Error: No document"

        try:
            pathroot = self._documentController.win.pathroot
            selectionGroup = pathroot.strandItemSelectionGroup()
            selectionGroup.clearSelection(False)
        except Exception:
            # Fallback: clear model selection directly
            selectionDict = doc.selectionDict()
            for strandSetDict in list(selectionDict.values()):
                for strand in list(strandSetDict.keys()):
                    doc.removeStrandFromSelection(strand)
            doc.updateSelection()
        return "Selection cleared"

    def selectStrand(self, helix_num, idx, strand_type, select_low=True, select_high=True):
        """
        Programmatically select a strand or part of a strand.

        Args:
            helix_num (int): Virtual helix number
            idx (int): Any index within the strand
            strand_type (str): "scaffold" or "staple"
            select_low (bool): Select the low endpoint
            select_high (bool): Select the high endpoint

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        if strand_type.lower() == "scaffold":
            strandSet = vh.scaffoldStrandSet()
        else:
            strandSet = vh.stapleStrandSet()

        strand = strandSet.getStrand(idx)
        if strand is None:
            return f"Error: No {strand_type} strand at helix {helix_num} index {idx}"

        doc = self.document
        doc.addStrandToSelection(strand, (select_low, select_high))
        doc.updateSelection()

        idxL, idxH = strand.idxs()
        return f"Selected {strand_type} strand on helix {helix_num} [{idxL}-{idxH}]"

    def selectEndpoint(self, helix_num, idx, strand_type, which_end):
        """
        Select a single endpoint of a strand.

        Selecting just one endpoint means moveSelection will extend/shrink
        the strand at that end while the other end stays fixed.

        Args:
            helix_num (int): Virtual helix number
            idx (int): Any index within the strand to identify it
            strand_type (str): "scaffold" or "staple"
            which_end (str): "low" or "high" — which endpoint to select

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        if strand_type.lower() == "scaffold":
            strandSet = vh.scaffoldStrandSet()
        else:
            strandSet = vh.stapleStrandSet()

        strand = strandSet.getStrand(idx)
        if strand is None:
            return f"Error: No {strand_type} strand at helix {helix_num} index {idx}"

        if which_end.lower() == "low":
            value = (True, False)
        elif which_end.lower() == "high":
            value = (False, True)
        else:
            return f"Error: which_end must be 'low' or 'high', got '{which_end}'"

        doc = self.document
        doc.addStrandToSelection(strand, value)
        doc.updateSelection()

        idxL, idxH = strand.idxs()
        endpoint_idx = idxL if which_end.lower() == "low" else idxH
        has_xover = (strand.connectionLow() is not None) if which_end.lower() == "low" else (strand.connectionHigh() is not None)
        xover_note = " (has crossover)" if has_xover else ""
        return f"Selected {which_end} endpoint of {strand_type} strand on helix {helix_num} [{idxL}-{idxH}] at index {endpoint_idx}{xover_note}"

    def selectCrossover(self, helix1, helix2, idx, strand_type):
        """
        Select a crossover between two helices at a given index.

        This selects the crossover endpoints on both connected strands,
        mirroring the behavior of clicking a crossover in the GUI.
        After selecting, moveSelection(delta) will move the crossover
        to the next valid lattice position, resizing both strands.

        Args:
            helix1 (int): First helix number
            helix2 (int): Second helix number
            idx (int): Index of the crossover on helix1
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
        else:
            ss1 = vh1.stapleStrandSet()

        strand = ss1.getStrand(idx)
        if strand is None:
            return f"Error: No {strand_type} strand at helix {helix1} index {idx}"

        # Determine which end of the strand has the crossover to helix2
        lo, hi = strand.idxs()
        connected_strand = None
        if idx == lo and strand.connectionLow():
            partner = strand.connectionLow()
            if partner.virtualHelix().number() == helix2:
                connected_strand = partner
        if idx == hi and strand.connectionHigh():
            partner = strand.connectionHigh()
            if partner.virtualHelix().number() == helix2:
                connected_strand = partner

        if connected_strand is None:
            return (f"Error: No crossover from helix {helix1} to helix {helix2} "
                    f"at index {idx}")

        # Replicate XoverItem.modelSelect logic:
        # The crossover is a connection from strand (5p side) to connected_strand (3p side).
        # For the 5p strand: select the high endpoint if drawn 5to3, else the low endpoint.
        # For the 3p strand: select the low endpoint if drawn 5to3, else the high endpoint.
        doc = self.document

        # strand on helix1: the crossover is at the endpoint connecting to helix2
        test1 = doc.isModelStrandSelected(strand)
        lowVal1, highVal1 = doc.getSelectedStrandValue(strand) if test1 else (False, False)
        if idx == lo:
            lowVal1 = True
        else:
            highVal1 = True

        # connected_strand on helix2
        test2 = doc.isModelStrandSelected(connected_strand)
        lowVal2, highVal2 = doc.getSelectedStrandValue(connected_strand) if test2 else (False, False)
        conn_lo, conn_hi = connected_strand.idxs()
        # The crossover connects at the partner's endpoint closest to idx
        if connected_strand.connectionLow() == strand:
            lowVal2 = True
        elif connected_strand.connectionHigh() == strand:
            highVal2 = True
        else:
            # Fallback: check by index
            if idx == conn_lo:
                lowVal2 = True
            else:
                highVal2 = True

        doc.addStrandToSelection(strand, (lowVal1, highVal1))
        doc.addStrandToSelection(connected_strand, (lowVal2, highVal2))
        doc.updateSelection()

        conn_lo, conn_hi = connected_strand.idxs()
        return (f"Selected {strand_type} crossover between helix {helix1}[{idx}] "
                f"and helix {helix2}[{conn_lo if lowVal2 else conn_hi}]")

    def listCrossovers(self, helix_num=None, strand_type=None):
        """
        List all existing crossovers in the design.

        Args:
            helix_num (int, optional): Filter to crossovers involving this helix
            strand_type (str, optional): Filter to "scaffold" or "staple"

        Returns:
            str: JSON-formatted list of crossovers with properties
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vhs = part.getVirtualHelices()
        crossovers = []
        seen = set()  # avoid duplicates (each xover connects two strands)

        for vh in vhs:
            vh_num = vh.number()
            if helix_num is not None and vh_num != helix_num:
                continue

            strand_sets = []
            if strand_type is None or strand_type.lower() == "scaffold":
                strand_sets.append(("scaffold", vh.scaffoldStrandSet()))
            if strand_type is None or strand_type.lower() == "staple":
                strand_sets.append(("staple", vh.stapleStrandSet()))

            for stype, ss in strand_sets:
                for strand in ss:
                    lo, hi = strand.idxs()
                    # Check low endpoint
                    if strand.connectionLow():
                        partner = strand.connectionLow()
                        partner_vh = partner.virtualHelix().number()
                        partner_lo, partner_hi = partner.idxs()
                        # Use the partner's endpoint index that connects back
                        if partner.connectionLow() == strand:
                            partner_idx = partner_lo
                        else:
                            partner_idx = partner_hi
                        key = tuple(sorted([(vh_num, lo), (partner_vh, partner_idx)]))
                        if key not in seen:
                            seen.add(key)
                            crossovers.append({
                                "helix1": vh_num,
                                "idx1": lo,
                                "helix2": partner_vh,
                                "idx2": partner_idx,
                                "strand_type": stype
                            })
                    # Check high endpoint
                    if strand.connectionHigh():
                        partner = strand.connectionHigh()
                        partner_vh = partner.virtualHelix().number()
                        partner_lo, partner_hi = partner.idxs()
                        if partner.connectionLow() == strand:
                            partner_idx = partner_lo
                        else:
                            partner_idx = partner_hi
                        key = tuple(sorted([(vh_num, hi), (partner_vh, partner_idx)]))
                        if key not in seen:
                            seen.add(key)
                            crossovers.append({
                                "helix1": vh_num,
                                "idx1": hi,
                                "helix2": partner_vh,
                                "idx2": partner_idx,
                                "strand_type": stype
                            })

        crossovers.sort(key=lambda x: (x["helix1"], x["helix2"], x["idx1"]))

        filter_desc = ""
        if helix_num is not None:
            filter_desc += f" on helix {helix_num}"
        if strand_type is not None:
            filter_desc += f" ({strand_type})"

        return f"Crossovers{filter_desc} ({len(crossovers)} total): {crossovers}"

    # ==================== STRAND PRIMITIVES ====================

    def listStrands(self, helix_num=None, strand_type=None):
        """
        List all strands in the design with their properties.
        This is a key primitive for iterating over strands.

        Args:
            helix_num (int, optional): Filter to specific helix
            strand_type (str, optional): Filter to "scaffold" or "staple"

        Returns:
            str: JSON-formatted list of all strands with properties
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        strands = []
        vhs = [part.virtualHelix(helix_num)] if helix_num is not None else part.getVirtualHelices()

        for vh in vhs:
            if vh is None:
                continue
            helix = vh.number()
            row, col = vh.coord()
            parity = "even" if row % 2 == col % 2 else "odd"

            strand_sets = []
            if strand_type is None or strand_type.lower() == "scaffold":
                strand_sets.append(("scaffold", vh.scaffoldStrandSet()))
            if strand_type is None or strand_type.lower() == "staple":
                strand_sets.append(("staple", vh.stapleStrandSet()))

            for stype, ss in strand_sets:
                for strand in ss:
                    lo, hi = strand.idxs()
                    strands.append({
                        "helix": helix,
                        "type": stype,
                        "low_idx": lo,
                        "high_idx": hi,
                        "length": hi - lo + 1,
                        "parity": parity,
                        "has_xover_low": strand.connectionLow() is not None,
                        "has_xover_high": strand.connectionHigh() is not None
                    })

        return f"Strands ({len(strands)} total): {strands}"

    def getStrandAt(self, helix_num, idx, strand_type):
        """
        Get information about the strand at a specific location.

        Args:
            helix_num (int): Virtual helix number
            idx (int): Base index (any index within the strand)
            strand_type (str): "scaffold" or "staple"

        Returns:
            str: Strand info or error if not found
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        if strand_type.lower() == "scaffold":
            ss = vh.scaffoldStrandSet()
        else:
            ss = vh.stapleStrandSet()

        strand = ss.getStrand(idx)
        if strand is None:
            return f"No {strand_type} strand at helix {helix_num} index {idx}"

        lo, hi = strand.idxs()
        row, col = vh.coord()
        parity = "even" if row % 2 == col % 2 else "odd"

        info = {
            "helix": helix_num,
            "type": strand_type,
            "low_idx": lo,
            "high_idx": hi,
            "length": hi - lo + 1,
            "parity": parity,
            "has_xover_low": strand.connectionLow() is not None,
            "has_xover_high": strand.connectionHigh() is not None
        }

        # Add connection details if present
        if strand.connectionLow():
            conn = strand.connectionLow()
            info["xover_low_to"] = {
                "helix": conn.virtualHelix().number(),
                "idx": conn.idx5Prime() if conn.isDrawn5to3() else conn.idx3Prime()
            }
        if strand.connectionHigh():
            conn = strand.connectionHigh()
            info["xover_high_to"] = {
                "helix": conn.virtualHelix().number(),
                "idx": conn.idx5Prime() if conn.isDrawn5to3() else conn.idx3Prime()
            }

        return f"Strand: {info}"

    def resizeStrand(self, helix_num, idx, strand_type, new_low, new_high):
        """
        Resize a strand by setting new endpoint indices.
        This is the primitive for moving/extending/shortening strands.

        Args:
            helix_num (int): Virtual helix number
            idx (int): Any index within the strand to identify it
            strand_type (str): "scaffold" or "staple"
            new_low (int): New low index
            new_high (int): New high index

        Returns:
            str: Success message or error
        """
        from cadnano2.model.strand import Strand

        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        if strand_type.lower() == "scaffold":
            ss = vh.scaffoldStrandSet()
        else:
            ss = vh.stapleStrandSet()

        strand = ss.getStrand(idx)
        if strand is None:
            return f"Error: No {strand_type} strand at helix {helix_num} index {idx}"

        old_lo, old_hi = strand.idxs()

        if new_low > new_high:
            return f"Error: new_low ({new_low}) cannot be greater than new_high ({new_high})"

        try:
            Strand.resize(strand, (new_low, new_high), useUndoStack=True)
            return f"Resized {strand_type} strand on helix {helix_num} from [{old_lo}-{old_hi}] to [{new_low}-{new_high}]"
        except Exception as e:
            return f"Error resizing strand: {e}"

    def deleteStrand(self, helix_num, idx, strand_type):
        """
        Delete a strand segment.

        Args:
            helix_num (int): Virtual helix number
            idx (int): Any index within the strand to identify it
            strand_type (str): "scaffold" or "staple"

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        if strand_type.lower() == "scaffold":
            ss = vh.scaffoldStrandSet()
        else:
            ss = vh.stapleStrandSet()

        strand = ss.getStrand(idx)
        if strand is None:
            return f"Error: No {strand_type} strand at helix {helix_num} index {idx}"

        lo, hi = strand.idxs()

        try:
            # Remove connections first
            if strand.connectionLow():
                strand.connectionLow().remove(useUndoStack=True)
            if strand.connectionHigh():
                strand.connectionHigh().remove(useUndoStack=True)
            # Delete the strand
            ss.removeStrand(strand, useUndoStack=True)
            return f"Deleted {strand_type} strand on helix {helix_num} [{lo}-{hi}]"
        except Exception as e:
            return f"Error deleting strand: {e}"

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

    def deleteHelix(self, helix_num):
        """
        Delete a virtual helix and all its strands.

        Args:
            helix_num (int): The virtual helix number to delete

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        row, col = vh.coord()

        try:
            part.removeVirtualHelix(vh, useUndoStack=True)
            return f"Deleted helix {helix_num} at ({row}, {col})"
        except Exception as e:
            return f"Error deleting helix: {e}"

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

    def _getDoubleCrossoverPair(self, part, vh1, vh2, idx, strand_type):
        """Find the paired index for a double crossover.

        Given one index of a crossover, returns the paired Low/High index
        from the honeycomb crossover tables.

        Returns:
            int or None: The paired index, or None if not found.
        """
        neighbors = part.getVirtualHelixNeighbors(vh1)
        if vh2 not in neighbors:
            return None
        direction = neighbors.index(vh2)

        if strand_type.lower() == "scaffold":
            low_positions = Crossovers.honeycombScafLow[direction]
            high_positions = Crossovers.honeycombScafHigh[direction]
        else:
            low_positions = Crossovers.honeycombStapLow[direction]
            high_positions = Crossovers.honeycombStapHigh[direction]

        step = part._step
        base = (idx // step) * step
        mod = idx % step

        # Find which pair this index belongs to and return the other
        for low, high in zip(low_positions, high_positions):
            if mod == low:
                return base + high
            elif mod == high:
                return base + low
        return None

    def createCrossover(self, helix1, idx1, helix2, idx2, strand_type):
        """
        Create a double crossover between two helices.

        A double crossover consists of two half-crossovers at adjacent
        positions (the Low/High pair). This is the standard crossover
        in DNA origami. The provided index is used to find the paired
        position automatically.

        Args:
            helix1 (int): First helix number
            idx1 (int): Index on first helix (either the Low or High position)
            helix2 (int): Second helix number
            idx2 (int): Index on second helix (must equal idx1)
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

        # Find the paired index for the double crossover
        paired_idx = self._getDoubleCrossoverPair(part, vh1, vh2, idx1, strand_type)
        if paired_idx is None:
            return (f"Error: Index {idx1} is not a valid {strand_type} crossover "
                    f"position between helix {helix1} and helix {helix2}")

        low_idx = min(idx1, paired_idx)
        high_idx = max(idx1, paired_idx)

        if strand_type.lower() == "scaffold":
            get_ss = lambda vh: vh.scaffoldStrandSet()
        else:
            get_ss = lambda vh: vh.stapleStrandSet()

        # Determine parity so xover direction is always even→odd at Low
        # and odd→even at High, regardless of argument order.
        vh_even = vh1 if vh1.isEvenParity() else vh2
        vh_odd  = vh2 if vh1.isEvenParity() else vh1

        # Both half-crossovers in one undo macro so a single undo reverts both.
        # At Low:  even-parity helix is 5p (its 3' end arrives at the crossover)
        # At High: odd-parity helix is 5p (its 3' end arrives at the crossover)
        xover_pairs = [
            (vh_even, vh_odd, low_idx),   # Low half-crossover: even → odd
            (vh_odd, vh_even, high_idx),  # High half-crossover: odd → even
        ]

        part.undoStack().beginMacro("Create Double Crossover")
        try:
            for vh_5p, vh_3p, idx in xover_pairs:
                s5p = get_ss(vh_5p).getStrand(idx)
                s3p = get_ss(vh_3p).getStrand(idx)
                if s5p is None:
                    part.undoStack().endMacro()
                    part.undoStack().undo()
                    return f"Error: No {strand_type} strand at helix {vh_5p.number()} index {idx}"
                if s3p is None:
                    part.undoStack().endMacro()
                    part.undoStack().undo()
                    return f"Error: No {strand_type} strand at helix {vh_3p.number()} index {idx}"
                part.createXover(s5p, idx, s3p, idx, useUndoStack=True)
            part.undoStack().endMacro()
        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error creating double crossover: {e}"

        return (f"Created {strand_type} double crossover: helix {helix1} <-> "
                f"helix {helix2} at indices [{low_idx}, {high_idx}]")

    def createHalfCrossover(self, helix1, idx1, helix2, idx2, strand_type):
        """
        Create a single half-crossover between two helices.

        Most of the time you want createCrossover (double crossover) instead.
        Only use this for explicit half-crossover requests.

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
            return f"Created {strand_type} half-crossover: helix {helix1}[{idx1}] <-> helix {helix2}[{idx2}]"
        except Exception as e:
            return f"Error creating half-crossover: {e}"

    def removeCrossover(self, helix_num, idx, strand_type):
        """
        Remove a crossover at the specified location.

        Args:
            helix_num (int): Helix number where the crossover is
            idx (int): Index of the crossover
            strand_type (str): "scaffold" or "staple"

        Returns:
            str: Success message or error
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        if strand_type.lower() == "scaffold":
            ss = vh.scaffoldStrandSet()
        else:
            ss = vh.stapleStrandSet()

        strand = ss.getStrand(idx)
        if strand is None:
            return f"Error: No {strand_type} strand at helix {helix_num} index {idx}"

        lo, hi = strand.idxs()

        # Check which endpoint was targeted and remove the crossover via Part API
        conn = None
        if idx == lo:
            conn = strand.connectionLow()
        elif idx == hi:
            conn = strand.connectionHigh()

        if conn is None:
            return f"No crossover found at helix {helix_num} index {idx}"

        other_vh = conn.virtualHelix().number()
        try:
            if strand.connection3p() == conn:
                part.removeXover(strand, conn, useUndoStack=True)
            elif strand.connection5p() == conn:
                part.removeXover(conn, strand, useUndoStack=True)
            else:
                return (
                    f"Error: endpoint at helix {helix_num}[{idx}] is not "
                    f"part of a valid crossover"
                )
            return (
                f"Removed crossover at helix {helix_num}[{idx}] "
                f"(was connected to helix {other_vh})"
            )
        except Exception as e:
            return f"Error removing crossover: {e}"

    def moveCrossover(self, helix1, helix2, idx, strand_type, delta):
        """
        Move a crossover by delta base pairs, bypassing lattice snap-to.

        Unlike moveSelection which snaps crossovers to the next valid
        lattice position, this method moves the crossover by exactly
        delta bases. It removes the crossover(s), resizes the strands,
        and recreates the crossover(s) at the new position.

        For a double crossover, both half-crossovers move by delta.

        The only constraint enforced is topology: the move is rejected
        if it would cause a strand to overlap a neighboring strand.

        Args:
            helix1 (int): First helix number
            helix2 (int): Second helix number
            idx (int): Index of one half-crossover on helix1
            strand_type (str): "scaffold" or "staple"
            delta (int): Base pairs to move (positive = right, negative = left)

        Returns:
            str: Success message or error
        """
        from cadnano2.model.strand import Strand

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

        strand1 = ss1.getStrand(idx)
        if strand1 is None:
            return f"Error: No {strand_type} strand at helix {helix1} index {idx}"

        # Find which endpoint on strand1 has the crossover to helix2
        lo1, hi1 = strand1.idxs()
        xover_at_low1 = (idx == lo1 and strand1.connectionLow() and
                         strand1.connectionLow().virtualHelix().number() == helix2)
        xover_at_high1 = (idx == hi1 and strand1.connectionHigh() and
                          strand1.connectionHigh().virtualHelix().number() == helix2)
        if not xover_at_low1 and not xover_at_high1:
            return (f"Error: No crossover from helix {helix1} to helix {helix2} "
                    f"at index {idx}")

        if xover_at_low1:
            partner1 = strand1.connectionLow()
        else:
            partner1 = strand1.connectionHigh()

        # Determine the partner's crossover endpoint index
        p1_lo, p1_hi = partner1.idxs()
        if partner1.connectionLow() == strand1:
            partner1_xover_at_low = True
            partner1_idx = p1_lo
        else:
            partner1_xover_at_low = False
            partner1_idx = p1_hi

        # Check if this is part of a double crossover (look for paired half-xover)
        paired_idx = self._getDoubleCrossoverPair(part, vh1, vh2, idx, strand_type)
        is_double = False
        strand2 = None
        partner2 = None

        if paired_idx is not None:
            strand2 = ss1.getStrand(paired_idx)
            if strand2 is not None:
                lo2, hi2 = strand2.idxs()
                xover2_low = (paired_idx == lo2 and strand2.connectionLow() and
                              strand2.connectionLow().virtualHelix().number() == helix2)
                xover2_high = (paired_idx == hi2 and strand2.connectionHigh() and
                               strand2.connectionHigh().virtualHelix().number() == helix2)
                if xover2_low:
                    partner2 = strand2.connectionLow()
                    is_double = True
                elif xover2_high:
                    partner2 = strand2.connectionHigh()
                    is_double = True

        # Collect all (strand, is_xover_at_low, current_xover_idx) tuples
        # Each crossover endpoint needs its strand resized
        xover_endpoints = []
        # First half-crossover: strand1 side
        xover_endpoints.append((strand1, xover_at_low1, idx))
        # First half-crossover: partner1 side
        xover_endpoints.append((partner1, partner1_xover_at_low, partner1_idx))

        if is_double:
            lo2, hi2 = strand2.idxs()
            strand2_at_low = (paired_idx == lo2)
            xover_endpoints.append((strand2, strand2_at_low, paired_idx))
            p2_lo, p2_hi = partner2.idxs()
            if partner2.connectionLow() == strand2:
                partner2_at_low = True
                partner2_idx = p2_lo
            else:
                partner2_at_low = False
                partner2_idx = p2_hi
            xover_endpoints.append((partner2, partner2_at_low, partner2_idx))

        # Validate bounds for all strands being resized
        for strand, at_low, xover_idx in xover_endpoints:
            lo, hi = strand.idxs()
            if at_low:
                new_lo = lo + delta
                new_hi = hi
                # Check: new_lo must not go below lower neighbor's high idx
                neighbors = strand.strandSet().getNeighbors(strand)
                if neighbors[0]:
                    if new_lo <= neighbors[0].highIdx():
                        return (f"Error: Moving by {delta} would overlap "
                                f"neighboring strand on helix "
                                f"{strand.virtualHelix().number()} "
                                f"(bound: {neighbors[0].highIdx() + 1})")
                elif new_lo < part.minBaseIdx():
                    return f"Error: Moving by {delta} would go below minimum index"
                if new_lo > new_hi:
                    return f"Error: Moving by {delta} would make strand length negative"
            else:
                new_lo = lo
                new_hi = hi + delta
                neighbors = strand.strandSet().getNeighbors(strand)
                if neighbors[1]:
                    if new_hi >= neighbors[1].lowIdx():
                        return (f"Error: Moving by {delta} would overlap "
                                f"neighboring strand on helix "
                                f"{strand.virtualHelix().number()} "
                                f"(bound: {neighbors[1].lowIdx() - 1})")
                elif new_hi > part.maxBaseIdx():
                    return f"Error: Moving by {delta} would exceed maximum index"
                if new_lo > new_hi:
                    return f"Error: Moving by {delta} would make strand length negative"

        # All checks passed — execute the move in one undo macro
        part.undoStack().beginMacro("Move Crossover")
        try:
            # Step 1: Remove crossover connections
            if xover_at_low1:
                s5p, s3p = (strand1, partner1) if strand1.connection5p() == partner1 \
                            else (partner1, strand1)
            else:
                s5p, s3p = (strand1, partner1) if strand1.connection3p() == partner1 \
                            else (partner1, strand1)
            part.removeXover(s5p, s3p, useUndoStack=True)

            if is_double:
                lo2, hi2 = strand2.idxs()
                strand2_at_low = (paired_idx == lo2)
                if strand2_at_low:
                    s5p2, s3p2 = (strand2, partner2) if strand2.connection5p() == partner2 \
                                  else (partner2, strand2)
                else:
                    s5p2, s3p2 = (strand2, partner2) if strand2.connection3p() == partner2 \
                                  else (partner2, strand2)
                part.removeXover(s5p2, s3p2, useUndoStack=True)

            # Step 2: Resize all strands
            for strand, at_low, xover_idx in xover_endpoints:
                lo, hi = strand.idxs()
                if at_low:
                    Strand.resize(strand, (lo + delta, hi), useUndoStack=True)
                else:
                    Strand.resize(strand, (lo, hi + delta), useUndoStack=True)

            # Step 3: Recreate crossover connections at new positions
            new_idx = idx + delta
            new_strand1 = ss1.getStrand(new_idx)
            new_partner1 = ss2.getStrand(partner1_idx + delta)
            if new_strand1 is None or new_partner1 is None:
                part.undoStack().endMacro()
                part.undoStack().undo()
                return f"Error: Could not find strands at new positions after resize"
            part.createXover(new_strand1, new_idx, new_partner1, partner1_idx + delta,
                             useUndoStack=True)

            if is_double:
                new_paired_idx = paired_idx + delta
                new_strand2 = ss1.getStrand(new_paired_idx)
                new_partner2 = ss2.getStrand(partner2_idx + delta)
                if new_strand2 is None or new_partner2 is None:
                    part.undoStack().endMacro()
                    part.undoStack().undo()
                    return f"Error: Could not find strands at new positions for paired crossover"
                part.createXover(new_strand2, new_paired_idx, new_partner2,
                                 partner2_idx + delta, useUndoStack=True)

            part.undoStack().endMacro()
        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error moving crossover: {e}"

        if is_double:
            new_low = min(idx + delta, paired_idx + delta)
            new_high = max(idx + delta, paired_idx + delta)
            return (f"Moved {strand_type} double crossover between helix {helix1} "
                    f"and helix {helix2} by {delta}bp to indices "
                    f"[{new_low}, {new_high}]")
        else:
            return (f"Moved {strand_type} half-crossover between helix {helix1} "
                    f"and helix {helix2} by {delta}bp to index {idx + delta}")

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

    # ==================== LEVEL 2: CONSTRAINT-AWARE QUERY TOOLS ====================

    def describeHelix(self, helix_num):
        """
        Rich single-call description of a helix: parity, strand directions,
        neighbors with direction labels, all strands with crossover connections,
        and valid crossover positions for each neighbor.

        Args:
            helix_num (int): The virtual helix number

        Returns:
            dict or str: Comprehensive helix description
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        row, col = vh.coord()
        even = part.isEvenParity(row, col)
        scafSS = vh.scaffoldStrandSet()
        stapSS = vh.stapleStrandSet()

        # Parity and directions
        info = {
            'helix_num': helix_num,
            'row': row,
            'col': col,
            'parity': 'even' if even else 'odd',
            'scaffold_5to3': 'left-to-right' if vh.isDrawn5to3(scafSS) else 'right-to-left',
            'staple_5to3': 'left-to-right' if vh.isDrawn5to3(stapSS) else 'right-to-left',
        }

        # Neighbors with direction labels
        neighbors = part.getVirtualHelixNeighbors(vh)
        neighbor_info = []
        for i, n in enumerate(neighbors):
            if n is not None:
                n_row, n_col = n.coord()
                neighbor_info.append({
                    'direction': f'p{i}',
                    'helix_num': n.number(),
                    'row': n_row,
                    'col': n_col,
                    'parity': 'even' if part.isEvenParity(n_row, n_col) else 'odd'
                })
        info['neighbors'] = neighbor_info

        # All strands with crossover connections
        def _strand_info(strand, stype):
            lo, hi = strand.idxs()
            s = {'type': stype, 'low': lo, 'high': hi, 'length': hi - lo + 1}
            if strand.connectionLow():
                conn = strand.connectionLow()
                s['xover_low'] = {'helix': conn.virtualHelix().number()}
            if strand.connectionHigh():
                conn = strand.connectionHigh()
                s['xover_high'] = {'helix': conn.virtualHelix().number()}
            return s

        strands = []
        for strand in scafSS:
            strands.append(_strand_info(strand, 'scaffold'))
        for strand in stapSS:
            strands.append(_strand_info(strand, 'staple'))
        info['strands'] = strands

        # Valid crossover positions for each neighbor
        xover_positions = []
        step = part._step
        for i, n in enumerate(neighbors):
            if n is None:
                continue
            direction = f'p{i}'
            scaf_low = Crossovers.honeycombScafLow[i]
            scaf_high = Crossovers.honeycombScafHigh[i]
            stap_low = Crossovers.honeycombStapLow[i]
            stap_high = Crossovers.honeycombStapHigh[i]
            xover_positions.append({
                'neighbor': n.number(),
                'direction': direction,
                'scaffold_positions_mod': sorted(scaf_low + scaf_high),
                'staple_positions_mod': sorted(stap_low + stap_high),
            })
        info['crossover_rules'] = xover_positions

        return info

    def analyzeDesign(self):
        """
        Comprehensive one-call state dump of the entire design.
        Returns all helices, strands, crossovers, potential crossover
        positions, and verifier warnings.

        Returns:
            dict or str: Full design analysis
        """
        part = self.activePart
        if part is None:
            return "Error: No active part. Create a Honeycomb or Square part first."

        vhs = part.getVirtualHelices()
        if not vhs:
            return {
                'helix_count': 0,
                'helices': [],
                'strands': [],
                'crossovers': [],
                'potential_crossovers': [],
                'issues': ['No helices in design'],
                'part_size': f"0-{part.maxBaseIdx()}, step={part._step}"
            }

        # Helices
        helices = []
        for vh in vhs:
            row, col = vh.coord()
            helices.append({
                'num': vh.number(),
                'row': row,
                'col': col,
                'parity': 'even' if part.isEvenParity(row, col) else 'odd'
            })

        # Strands
        strands = []
        for vh in vhs:
            h = vh.number()
            for strand in vh.scaffoldStrandSet():
                lo, hi = strand.idxs()
                s = {'helix': h, 'type': 'scaffold', 'low': lo, 'high': hi}
                if strand.connectionLow():
                    s['xover_low'] = strand.connectionLow().virtualHelix().number()
                if strand.connectionHigh():
                    s['xover_high'] = strand.connectionHigh().virtualHelix().number()
                strands.append(s)
            for strand in vh.stapleStrandSet():
                lo, hi = strand.idxs()
                s = {'helix': h, 'type': 'staple', 'low': lo, 'high': hi}
                if strand.connectionLow():
                    s['xover_low'] = strand.connectionLow().virtualHelix().number()
                if strand.connectionHigh():
                    s['xover_high'] = strand.connectionHigh().virtualHelix().number()
                strands.append(s)

        # Existing crossovers (deduplicated)
        crossovers = []
        seen = set()
        for vh in vhs:
            h = vh.number()
            for stype, ss in [('scaffold', vh.scaffoldStrandSet()),
                              ('staple', vh.stapleStrandSet())]:
                for strand in ss:
                    lo, hi = strand.idxs()
                    for end, conn_fn in [('low', strand.connectionLow),
                                         ('high', strand.connectionHigh)]:
                        conn = conn_fn()
                        if conn is None:
                            continue
                        other_h = conn.virtualHelix().number()
                        idx = lo if end == 'low' else hi
                        key = tuple(sorted([(h, idx), (other_h, conn.idxs()[0 if conn.connectionLow() == strand else 1])]))
                        if key not in seen:
                            seen.add(key)
                            crossovers.append({
                                'helix1': h, 'idx1': idx,
                                'helix2': other_h, 'strand_type': stype
                            })

        # Neighbor pairs with unused crossover positions
        potential = []
        for vh in vhs:
            neighbors = part.getVirtualHelixNeighbors(vh)
            for i, n in enumerate(neighbors):
                if n is None or n.number() < vh.number():
                    continue  # skip to avoid duplicates
                potential.append({
                    'helix1': vh.number(),
                    'helix2': n.number(),
                    'direction': f'p{i}'
                })

        # Verifier issues
        verifier = DesignVerifier(self._documentController)
        result = verifier.verifyDesign()

        return {
            'helix_count': len(vhs),
            'helices': helices,
            'strand_count': len(strands),
            'strands': strands,
            'crossover_count': len(crossovers),
            'crossovers': crossovers,
            'neighbor_pairs': potential,
            'issues': result.get('issues', []),
            'warnings': result.get('warnings', []),
            'design_quality': result.get('score', 0),
            'part_size': f"0-{part.maxBaseIdx()}, step={part._step}"
        }

    def suggestCrossovers(self, helix1, helix2, strand_type, min_spacing=21):
        """
        Return valid crossover positions between two helices, annotated with
        occupancy and spacing recommendations.

        Args:
            helix1 (int): First helix number
            helix2 (int): Second helix number
            strand_type (str): "scaffold" or "staple"
            min_spacing (int): Minimum bp between crossovers (default 21)

        Returns:
            dict or str: Annotated crossover suggestions
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

        neighbors = part.getVirtualHelixNeighbors(vh1)
        if vh2 not in neighbors:
            return f"Error: Helix {helix2} is not a neighbor of helix {helix1}"

        direction_idx = neighbors.index(vh2)
        step = part._step

        if strand_type.lower() == "scaffold":
            low_offsets = Crossovers.honeycombScafLow[direction_idx]
            high_offsets = Crossovers.honeycombScafHigh[direction_idx]
            get_ss1 = vh1.scaffoldStrandSet
            get_ss2 = vh2.scaffoldStrandSet
        else:
            low_offsets = Crossovers.honeycombStapLow[direction_idx]
            high_offsets = Crossovers.honeycombStapHigh[direction_idx]
            get_ss1 = vh1.stapleStrandSet
            get_ss2 = vh2.stapleStrandSet

        # Find strand ranges on both helices to know where crossovers are possible
        ss1 = get_ss1()
        ss2 = get_ss2()
        strands1 = [(s.idxs()[0], s.idxs()[1]) for s in ss1]
        strands2 = [(s.idxs()[0], s.idxs()[1]) for s in ss2]

        if not strands1 or not strands2:
            return {
                'helix1': helix1, 'helix2': helix2,
                'strand_type': strand_type,
                'error': 'Both helices need strands before crossovers can be added',
                'positions': []
            }

        # Determine the overlapping index range
        max_lo = max(min(s[0] for s in strands1), min(s[0] for s in strands2))
        min_hi = min(max(s[1] for s in strands1), max(s[1] for s in strands2))

        # Collect existing crossovers between these two helices
        occupied = set()
        for strand in ss1:
            lo, hi = strand.idxs()
            if strand.connectionLow() and strand.connectionLow().virtualHelix() == vh2:
                occupied.add(lo)
            if strand.connectionHigh() and strand.connectionHigh().virtualHelix() == vh2:
                occupied.add(hi)

        # Generate all valid positions within strand ranges
        positions = []
        max_idx = part.maxBaseIdx()
        for base in range(0, max_idx + 1, step):
            for low_off, high_off in zip(low_offsets, high_offsets):
                low_idx = base + low_off
                high_idx = base + high_off
                if low_idx < max_lo or high_idx > min_hi:
                    continue
                # Check both indices are within strands on both helices
                in_strand1 = any(lo <= low_idx <= hi and lo <= high_idx <= hi for lo, hi in strands1)
                in_strand2 = any(lo <= low_idx <= hi and lo <= high_idx <= hi for lo, hi in strands2)
                if not in_strand1 or not in_strand2:
                    continue
                is_occupied = low_idx in occupied or high_idx in occupied
                positions.append({
                    'low_idx': low_idx,
                    'high_idx': high_idx,
                    'occupied': is_occupied
                })

        # Apply spacing filter for recommendations
        available = [p for p in positions if not p['occupied']]
        recommended = []
        last_idx = -min_spacing
        for p in available:
            if p['low_idx'] - last_idx >= min_spacing:
                recommended.append(p['low_idx'])
                last_idx = p['low_idx']

        for p in positions:
            p['recommended'] = p['low_idx'] in recommended

        return {
            'helix1': helix1,
            'helix2': helix2,
            'strand_type': strand_type,
            'direction': f'p{direction_idx}',
            'min_spacing': min_spacing,
            'positions': positions,
            'available_count': len(available),
            'recommended_count': len(recommended)
        }

    def getNeighborPairs(self):
        """
        Return all neighbor pairs in the current design with their direction.

        Returns:
            list or str: List of neighbor pairs with direction info
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vhs = part.getVirtualHelices()
        if not vhs:
            return "No helices in design"

        pairs = []
        seen = set()
        for vh in vhs:
            neighbors = part.getVirtualHelixNeighbors(vh)
            for i, n in enumerate(neighbors):
                if n is None:
                    continue
                key = tuple(sorted([vh.number(), n.number()]))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append({
                    'helix1': vh.number(),
                    'helix2': n.number(),
                    'direction': f'p{i}'
                })

        return {'neighbor_pairs': pairs, 'count': len(pairs)}

    # ==================== LEVEL 2: BATCH EXECUTION TOOLS ====================

    # Canonical honeycomb bundle positions, centered around (21, 21).
    # The 6-helix bundle (and all larger bundles) use a 3-wide × 2-tall
    # arrangement so the slice view renders as a hexagon, not a vertical line.
    #
    # Rendering math  (scaleFactor = 15/1.125 = 13.33 px/nm, root3 = 1.732):
    #   x_screen = col × 25.98 px
    #   y_screen = row × 45 px  (+ 15 px if odd parity)
    #
    # 6-helix ring [(21,20)…(22,22)]:
    #   screen 52 px wide × 60 px tall  →  aspect ≈ 1.2 : 1  → hexagon ✓
    #   (old 2-wide × 3-tall was 26 px × 105 px  →  4 : 1  → vertical line ✗)
    _HONEYCOMB_BUNDLE_POSITIONS = {
        1:  [(21, 21)],
        2:  [(21, 21), (21, 22)],
        3:  [(21, 21), (21, 22), (22, 22)],
        4:  [(21, 21), (21, 22), (22, 22), (22, 21)],
        # 3-wide × 2-tall closed hexagonal ring — 6 ring edges, aspect 1.2:1
        6:  [(21, 20), (21, 21), (21, 22),
             (22, 20), (22, 21), (22, 22)],
        # 6-helix ring + 1 above-center spike at (20, 21)
        7:  [(20, 21),
             (21, 20), (21, 21), (21, 22),
             (22, 20), (22, 21), (22, 22)],
        19: [(19, 20), (19, 21), (19, 22),
             (20, 19), (20, 20), (20, 21), (20, 22), (20, 23),
             (21, 19), (21, 20), (21, 21), (21, 22), (21, 23),
             (22, 20), (22, 21), (22, 22), (22, 23),
             (23, 21), (23, 22)],
    }

    def createHelicesWithStrands(self, strand_type, length,
                                 positions=None, num_helices=None):
        """
        Create multiple helices with strands in one batch operation.
        Auto-extends part size if needed. Wraps in one undo macro.

        Provide EITHER num_helices (preferred — positions computed automatically)
        OR an explicit positions list of [row, col] pairs.

        Args:
            strand_type (str): "scaffold", "staple", or "both"
            length (int): Strand length in bases
            positions (list): Optional list of [row, col] pairs
            num_helices (int): Number of helices for a standard bundle (2, 6, 7, 19 …)

        Returns:
            dict or str: Summary of created helices and strands
        """
        # Resolve positions
        if positions is None:
            if num_helices is None:
                return "Error: Provide either num_helices or positions"
            if num_helices in self._HONEYCOMB_BUNDLE_POSITIONS:
                positions = self._HONEYCOMB_BUNDLE_POSITIONS[num_helices]
            else:
                # Fallback: pack into a 3-wide grid (matches hexagonal appearance)
                result = []
                for i in range(num_helices):
                    row = 21 + i // 3
                    col = 20 + (i % 3)
                    result.append((row, col))
                positions = result

        part = self.activePart
        if part is None:
            return "Error: No active part. Create a Honeycomb or Square part first."

        part.undoStack().beginMacro("Create Helices With Strands")
        try:
            # Auto-extend part size if needed
            if length - 1 > part.maxBaseIdx():
                from math import ceil
                step = part.stepSize()
                delta_needed = (length - 1) - part.maxBaseIdx()
                delta = int(ceil(delta_needed / step)) * step
                part.resizeVirtualHelices(0, delta, useUndoStack=True)

            created_helices = []
            for pos in positions:
                row, col = pos[0], pos[1]
                existing = part.virtualHelixAtCoord((row, col))
                if existing is not None:
                    part.undoStack().endMacro()
                    part.undoStack().undo()
                    return f"Error: Helix already exists at ({row}, {col}) with number {existing.number()}"

                part.createVirtualHelix(row, col, useUndoStack=True)
                vh = part.virtualHelixAtCoord((row, col))
                if vh is None:
                    part.undoStack().endMacro()
                    part.undoStack().undo()
                    return f"Error: Failed to create helix at ({row}, {col})"

                helix_num = vh.number()
                start_idx = 0
                end_idx = length - 1

                # Create strands
                strand_types_to_create = []
                if strand_type.lower() in ("scaffold", "both"):
                    strand_types_to_create.append(("scaffold", vh.scaffoldStrandSet()))
                if strand_type.lower() in ("staple", "both"):
                    strand_types_to_create.append(("staple", vh.stapleStrandSet()))

                for stype, ss in strand_types_to_create:
                    result = ss.createStrand(start_idx, end_idx, useUndoStack=True)
                    if result < 0:
                        part.undoStack().endMacro()
                        part.undoStack().undo()
                        return f"Error: Could not create {stype} strand on helix {helix_num}"

                created_helices.append({
                    'helix_num': helix_num,
                    'row': row,
                    'col': col,
                    'strand_range': [start_idx, end_idx]
                })

            part.undoStack().endMacro()

        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error creating helices with strands: {e}"

        return {
            'created': len(created_helices),
            'helices': created_helices,
            'strand_type': strand_type,
            'length': length
        }

    def addCrossoversForPair(self, helix1, helix2, strand_type, positions=None, spacing=21):
        """
        Add double crossovers between two helices. If positions is None,
        auto-computes valid positions with spacing constraint.

        Args:
            helix1 (int): First helix number
            helix2 (int): Second helix number
            strand_type (str): "scaffold" or "staple"
            positions (list, optional): Specific crossover indices (low idx of each pair)
            spacing (int): Minimum spacing between crossovers (default 21)

        Returns:
            dict or str: Summary of crossovers created
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

        neighbors = part.getVirtualHelixNeighbors(vh1)
        if vh2 not in neighbors:
            return f"Error: Helix {helix2} is not a neighbor of helix {helix1}"

        direction_idx = neighbors.index(vh2)
        step = part._step

        if strand_type.lower() == "scaffold":
            low_offsets = Crossovers.honeycombScafLow[direction_idx]
            high_offsets = Crossovers.honeycombScafHigh[direction_idx]
            get_ss = lambda vh: vh.scaffoldStrandSet()
        else:
            low_offsets = Crossovers.honeycombStapLow[direction_idx]
            high_offsets = Crossovers.honeycombStapHigh[direction_idx]
            get_ss = lambda vh: vh.stapleStrandSet()

        if positions is None:
            # Auto-compute: find all valid positions with spacing
            suggestions = self.suggestCrossovers(helix1, helix2, strand_type, spacing)
            if isinstance(suggestions, str):
                return suggestions  # error message
            positions = [p['low_idx'] for p in suggestions.get('positions', [])
                        if p.get('recommended') and not p.get('occupied')]

        if not positions:
            return {
                'helix1': helix1, 'helix2': helix2,
                'strand_type': strand_type,
                'created': 0,
                'message': 'No valid positions found for crossovers'
            }

        # Validate all positions before creating any
        for pos in positions:
            mod = pos % step
            if mod not in low_offsets and mod not in high_offsets:
                valid_mods = sorted(low_offsets + high_offsets)
                return (f"Error: Position {pos} (mod {step} = {mod}) is not a valid "
                        f"{strand_type} crossover for direction p{direction_idx}. "
                        f"Valid mods: {valid_mods}")

        part.undoStack().beginMacro(f"Add Crossovers {helix1}-{helix2}")
        try:
            created = []
            for pos in positions:
                # Find the paired index
                paired_idx = self._getDoubleCrossoverPair(part, vh1, vh2, pos, strand_type)
                if paired_idx is None:
                    continue

                low_idx = min(pos, paired_idx)
                high_idx = max(pos, paired_idx)

                # Verify strands exist at both indices on both helices
                ss1 = get_ss(vh1)
                ss2 = get_ss(vh2)

                # Parity-aware: even is 5p at Low, odd is 5p at High
                vh_even = vh1 if vh1.isEvenParity() else vh2
                vh_odd  = vh2 if vh1.isEvenParity() else vh1
                xover_pairs = [
                    (vh_even, vh_odd, low_idx),
                    (vh_odd, vh_even, high_idx),
                ]

                skip = False
                for vh_5p, vh_3p, idx in xover_pairs:
                    s5p = get_ss(vh_5p).getStrand(idx)
                    s3p = get_ss(vh_3p).getStrand(idx)
                    if s5p is None or s3p is None:
                        skip = True
                        break
                if skip:
                    continue

                for vh_5p, vh_3p, idx in xover_pairs:
                    s5p = get_ss(vh_5p).getStrand(idx)
                    s3p = get_ss(vh_3p).getStrand(idx)
                    part.createXover(s5p, idx, s3p, idx, useUndoStack=True)

                created.append({'low_idx': low_idx, 'high_idx': high_idx})

            part.undoStack().endMacro()

        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error creating crossovers: {e}"

        return {
            'helix1': helix1,
            'helix2': helix2,
            'strand_type': strand_type,
            'created': len(created),
            'crossovers': created
        }

    def addAllNeighborCrossovers(self, strand_type, spacing=21):
        """
        Add crossovers between all neighbor pairs in the design.
        One undo macro for the whole operation.

        Args:
            strand_type (str): "scaffold" or "staple"
            spacing (int): Minimum spacing between crossovers (default 21)

        Returns:
            dict or str: Summary with per-pair breakdown
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        pairs_info = self.getNeighborPairs()
        if isinstance(pairs_info, str):
            return pairs_info

        pairs = pairs_info.get('neighbor_pairs', [])
        if not pairs:
            return "Error: No neighbor pairs found"

        part.undoStack().beginMacro("Add All Neighbor Crossovers")
        try:
            total_created = 0
            pair_results = []

            for pair in pairs:
                h1, h2 = pair['helix1'], pair['helix2']
                result = self._addCrossoversForPairInternal(
                    part, h1, h2, strand_type, spacing
                )
                count = result.get('created', 0) if isinstance(result, dict) else 0
                total_created += count
                pair_results.append({
                    'helix1': h1,
                    'helix2': h2,
                    'created': count
                })

            part.undoStack().endMacro()

        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error adding all neighbor crossovers: {e}"

        return {
            'strand_type': strand_type,
            'total_created': total_created,
            'pairs': pair_results
        }

    def _addCrossoversForPairInternal(self, part, helix1, helix2, strand_type, spacing):
        """
        Internal helper for addAllNeighborCrossovers — creates crossovers
        between a pair without its own undo macro (caller wraps).
        """
        vh1 = part.virtualHelix(helix1)
        vh2 = part.virtualHelix(helix2)
        if vh1 is None or vh2 is None:
            return {'created': 0}

        neighbors = part.getVirtualHelixNeighbors(vh1)
        if vh2 not in neighbors:
            return {'created': 0}

        direction_idx = neighbors.index(vh2)

        if strand_type.lower() == "scaffold":
            low_offsets = Crossovers.honeycombScafLow[direction_idx]
            high_offsets = Crossovers.honeycombScafHigh[direction_idx]
            get_ss = lambda vh: vh.scaffoldStrandSet()
        else:
            low_offsets = Crossovers.honeycombStapLow[direction_idx]
            high_offsets = Crossovers.honeycombStapHigh[direction_idx]
            get_ss = lambda vh: vh.stapleStrandSet()

        # Auto-compute positions
        suggestions = self.suggestCrossovers(helix1, helix2, strand_type, spacing)
        if isinstance(suggestions, str):
            return {'created': 0}
        positions = [p['low_idx'] for p in suggestions.get('positions', [])
                    if p.get('recommended') and not p.get('occupied')]

        created = []
        for pos in positions:
            paired_idx = self._getDoubleCrossoverPair(part, vh1, vh2, pos, strand_type)
            if paired_idx is None:
                continue

            low_idx = min(pos, paired_idx)
            high_idx = max(pos, paired_idx)

            vh_even = vh1 if vh1.isEvenParity() else vh2
            vh_odd  = vh2 if vh1.isEvenParity() else vh1
            xover_pairs = [
                (vh_even, vh_odd, low_idx),
                (vh_odd, vh_even, high_idx),
            ]

            skip = False
            for vh_5p, vh_3p, idx in xover_pairs:
                s5p = get_ss(vh_5p).getStrand(idx)
                s3p = get_ss(vh_3p).getStrand(idx)
                if s5p is None or s3p is None:
                    skip = True
                    break
            if skip:
                continue

            for vh_5p, vh_3p, idx in xover_pairs:
                s5p = get_ss(vh_5p).getStrand(idx)
                s3p = get_ss(vh_3p).getStrand(idx)
                part.createXover(s5p, idx, s3p, idx, useUndoStack=True)

            created.append({'low_idx': low_idx, 'high_idx': high_idx})

        return {'created': len(created), 'crossovers': created}

    def resizeAllStrands(self, strand_type, new_length=None, delta=None, helix_num=None):
        """
        Resize all strands of a type in bulk. Respects parity for which end
        to resize. Wraps in one undo macro.

        Args:
            strand_type (str): "scaffold" or "staple"
            new_length (int, optional): Absolute new length
            delta (int, optional): Relative change in length
            helix_num (int, optional): Filter to one helix

        Returns:
            dict or str: Summary of resized strands
        """
        from cadnano2.model.strand import Strand

        if new_length is None and delta is None:
            return "Error: Provide either new_length or delta"

        part = self.activePart
        if part is None:
            return "Error: No active part"

        vhs = [part.virtualHelix(helix_num)] if helix_num is not None else part.getVirtualHelices()

        # Collect strands to resize
        to_resize = []
        for vh in vhs:
            if vh is None:
                continue
            row, col = vh.coord()
            even = part.isEvenParity(row, col)

            if strand_type.lower() == "scaffold":
                ss = vh.scaffoldStrandSet()
            else:
                ss = vh.stapleStrandSet()

            for strand in ss:
                lo, hi = strand.idxs()
                old_len = hi - lo + 1
                target_len = new_length if new_length is not None else old_len + delta

                if target_len < 1:
                    continue

                # Even parity: scaffold goes left→right, resize high end
                # Odd parity: scaffold goes right→left, resize low end
                if even:
                    new_lo = lo
                    new_hi = lo + target_len - 1
                else:
                    new_hi = hi
                    new_lo = hi - target_len + 1

                to_resize.append((strand, lo, hi, new_lo, new_hi, vh.number()))

        if not to_resize:
            return "No strands found to resize"

        part.undoStack().beginMacro("Resize All Strands")
        try:
            resized = []
            for strand, old_lo, old_hi, new_lo, new_hi, h_num in to_resize:
                if new_lo < part.minBaseIdx() or new_hi > part.maxBaseIdx():
                    continue
                Strand.resize(strand, (new_lo, new_hi), useUndoStack=True)
                resized.append({
                    'helix': h_num,
                    'old_range': [old_lo, old_hi],
                    'new_range': [new_lo, new_hi]
                })
            part.undoStack().endMacro()
        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error resizing strands: {e}"

        return {
            'strand_type': strand_type,
            'resized': len(resized),
            'strands': resized
        }

    def removeCrossoversForPair(self, helix1, helix2, strand_type):
        """
        Remove all crossovers between two helices for a given strand type.
        Wrapped in one undo macro for atomic undo.

        Args:
            helix1 (int): First helix number
            helix2 (int): Second helix number
            strand_type (str): "scaffold" or "staple"

        Returns:
            dict or str: Summary with count removed
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
            get_ss = lambda vh: vh.scaffoldStrandSet()
        else:
            get_ss = lambda vh: vh.stapleStrandSet()

        # Find all crossovers between the pair
        xovers_to_remove = []  # list of (strand_5p, strand_3p) tuples
        seen = set()

        for vh, other_num in [(vh1, helix2), (vh2, helix1)]:
            ss = get_ss(vh)
            for strand in ss:
                lo, hi = strand.idxs()
                for idx, conn_func in [(lo, strand.connectionLow), (hi, strand.connectionHigh)]:
                    conn = conn_func()
                    if conn is None:
                        continue
                    if conn.virtualHelix().number() != other_num:
                        continue
                    key = tuple(sorted([(vh.number(), idx),
                                        (conn.virtualHelix().number(),
                                         conn.idxs()[0] if conn.connectionLow() == strand else conn.idxs()[1])]))
                    if key in seen:
                        continue
                    seen.add(key)
                    if strand.connection3p() == conn:
                        xovers_to_remove.append((strand, conn))
                    elif strand.connection5p() == conn:
                        xovers_to_remove.append((conn, strand))

        if not xovers_to_remove:
            return {
                'helix1': helix1, 'helix2': helix2,
                'strand_type': strand_type,
                'removed': 0,
                'message': 'No crossovers found between this pair'
            }

        part.undoStack().beginMacro(f"Remove Crossovers {helix1}-{helix2}")
        try:
            removed = 0
            for s5p, s3p in xovers_to_remove:
                part.removeXover(s5p, s3p, useUndoStack=True)
                removed += 1
            part.undoStack().endMacro()
        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error removing crossovers: {e}"

        return {
            'helix1': helix1,
            'helix2': helix2,
            'strand_type': strand_type,
            'removed': removed
        }

    def removeAllCrossovers(self, strand_type):
        """
        Remove all crossovers of a given strand type from the entire design.
        Wrapped in one undo macro for atomic undo.

        Args:
            strand_type (str): "scaffold" or "staple"

        Returns:
            dict or str: Summary with count removed
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        if strand_type.lower() == "scaffold":
            get_ss = lambda vh: vh.scaffoldStrandSet()
        else:
            get_ss = lambda vh: vh.stapleStrandSet()

        # Collect all crossovers of this type
        xovers_to_remove = []  # list of (strand_5p, strand_3p) tuples
        seen = set()

        for vh in part.getVirtualHelices():
            vh_num = vh.number()
            ss = get_ss(vh)
            for strand in ss:
                lo, hi = strand.idxs()
                for idx, conn_func in [(lo, strand.connectionLow), (hi, strand.connectionHigh)]:
                    conn = conn_func()
                    if conn is None:
                        continue
                    partner_vh = conn.virtualHelix().number()
                    partner_lo, partner_hi = conn.idxs()
                    if conn.connectionLow() == strand:
                        partner_idx = partner_lo
                    else:
                        partner_idx = partner_hi
                    key = tuple(sorted([(vh_num, idx), (partner_vh, partner_idx)]))
                    if key in seen:
                        continue
                    seen.add(key)
                    if strand.connection3p() == conn:
                        xovers_to_remove.append((strand, conn))
                    elif strand.connection5p() == conn:
                        xovers_to_remove.append((conn, strand))

        if not xovers_to_remove:
            return {
                'strand_type': strand_type,
                'removed': 0,
                'message': 'No crossovers found'
            }

        part.undoStack().beginMacro(f"Remove All {strand_type} Crossovers")
        try:
            removed = 0
            for s5p, s3p in xovers_to_remove:
                part.removeXover(s5p, s3p, useUndoStack=True)
                removed += 1
            part.undoStack().endMacro()
        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error removing crossovers: {e}"

        return {
            'strand_type': strand_type,
            'removed': removed
        }

    def addInsertionPattern(self, helix_num, length, spacing=21,
                            start_idx=None, end_idx=None, strand_type=None):
        """
        Add insertions at regular intervals along a helix.
        Wrapped in one undo macro for atomic undo.

        Args:
            helix_num (int): Which helix
            length (int): Insertion length (positive) or deletion (-1)
            spacing (int): Interval between insertions (default 21)
            start_idx (int, optional): Starting index, defaults to first strand start
            end_idx (int, optional): Ending index, defaults to last strand end
            strand_type (str, optional): "scaffold" or "staple", defaults to
                whichever strand exists at each position

        Returns:
            dict or str: Summary with list of positions where insertions were added
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        scafSS = vh.scaffoldStrandSet()
        stapSS = vh.stapleStrandSet()

        # Determine range from existing strands if not specified
        if start_idx is None or end_idx is None:
            all_strands = []
            if strand_type is None or strand_type.lower() == "scaffold":
                all_strands.extend(list(scafSS))
            if strand_type is None or strand_type.lower() == "staple":
                all_strands.extend(list(stapSS))
            if not all_strands:
                return f"Error: No strands on helix {helix_num}"
            if start_idx is None:
                start_idx = min(s.idxs()[0] for s in all_strands)
            if end_idx is None:
                end_idx = max(s.idxs()[1] for s in all_strands)

        part.undoStack().beginMacro(f"Add Insertion Pattern h{helix_num}")
        try:
            added = []
            idx = start_idx
            while idx <= end_idx:
                # Find a strand at this position
                strand = None
                if strand_type is None or strand_type.lower() == "scaffold":
                    strand = scafSS.getStrand(idx)
                if strand is None and (strand_type is None or strand_type.lower() == "staple"):
                    strand = stapSS.getStrand(idx)

                if strand is None:
                    idx += spacing
                    continue

                # Skip if a crossover is at this exact position
                lo, hi = strand.idxs()
                if (idx == lo and strand.connectionLow()) or \
                   (idx == hi and strand.connectionHigh()):
                    idx += spacing
                    continue

                # Skip if there's already an insertion here
                if strand.hasInsertionAt(idx):
                    idx += spacing
                    continue

                strand.addInsertion(idx, length, useUndoStack=True)
                added.append(idx)
                idx += spacing

            part.undoStack().endMacro()
        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error adding insertion pattern: {e}"

        label = "deletions" if length < 0 else f"{length}-base insertions"
        return {
            'helix_num': helix_num,
            'length': length,
            'spacing': spacing,
            'added': len(added),
            'positions': added,
            'message': f"Added {len(added)} {label} on helix {helix_num}"
        }

    def removeInsertionPattern(self, helix_num, strand_type=None):
        """
        Remove ALL insertions/deletions from a helix.
        Wrapped in one undo macro for atomic undo.

        Args:
            helix_num (int): Which helix
            strand_type (str, optional): "scaffold" or "staple", or None for both

        Returns:
            dict or str: Summary with count removed
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return f"Error: Helix {helix_num} not found"

        scafSS = vh.scaffoldStrandSet()
        stapSS = vh.stapleStrandSet()

        # Collect all strands and their insertions
        insertions_to_remove = []  # list of (strand, idx)
        strand_sets = []
        if strand_type is None or strand_type.lower() == "scaffold":
            strand_sets.append(scafSS)
        if strand_type is None or strand_type.lower() == "staple":
            strand_sets.append(stapSS)

        for ss in strand_sets:
            for strand in ss:
                for insertion in strand.insertionsOnStrand():
                    insertions_to_remove.append((strand, insertion.idx()))

        if not insertions_to_remove:
            return {
                'helix_num': helix_num,
                'removed': 0,
                'message': f'No insertions found on helix {helix_num}'
            }

        part.undoStack().beginMacro(f"Remove Insertions h{helix_num}")
        try:
            removed = 0
            for strand, idx in insertions_to_remove:
                strand.removeInsertion(idx, useUndoStack=True)
                removed += 1
            part.undoStack().endMacro()
        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error removing insertions: {e}"

        return {
            'helix_num': helix_num,
            'removed': removed
        }

    def addInsertionPatternAll(self, length, spacing=21, strand_type=None):
        """
        Add insertions/deletions across ALL helices in the design.
        Wrapped in one undo macro for atomic undo.

        Args:
            length (int): Insertion length (positive) or deletion (-1)
            spacing (int): Interval between insertions (default 21)
            strand_type (str, optional): "scaffold" or "staple", or None for
                whichever strand exists at each position

        Returns:
            dict or str: Summary with per-helix breakdown
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vhs = part.getVirtualHelices()
        if not vhs:
            return "Error: No helices in design"

        part.undoStack().beginMacro("Add Insertion Pattern All Helices")
        try:
            total_added = 0
            per_helix = []

            for vh in vhs:
                vh_num = vh.number()
                scafSS = vh.scaffoldStrandSet()
                stapSS = vh.stapleStrandSet()

                # Determine range from existing strands
                all_strands = []
                if strand_type is None or strand_type.lower() == "scaffold":
                    all_strands.extend(list(scafSS))
                if strand_type is None or strand_type.lower() == "staple":
                    all_strands.extend(list(stapSS))
                if not all_strands:
                    continue

                start_idx = min(s.idxs()[0] for s in all_strands)
                end_idx = max(s.idxs()[1] for s in all_strands)

                added = []
                idx = start_idx
                while idx <= end_idx:
                    strand = None
                    if strand_type is None or strand_type.lower() == "scaffold":
                        strand = scafSS.getStrand(idx)
                    if strand is None and (strand_type is None or strand_type.lower() == "staple"):
                        strand = stapSS.getStrand(idx)

                    if strand is None:
                        idx += spacing
                        continue

                    lo, hi = strand.idxs()
                    if (idx == lo and strand.connectionLow()) or \
                       (idx == hi and strand.connectionHigh()):
                        idx += spacing
                        continue

                    if strand.hasInsertionAt(idx):
                        idx += spacing
                        continue

                    strand.addInsertion(idx, length, useUndoStack=True)
                    added.append(idx)
                    idx += spacing

                if added:
                    total_added += len(added)
                    per_helix.append({
                        'helix_num': vh_num,
                        'added': len(added),
                        'positions': added
                    })

            part.undoStack().endMacro()
        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return f"Error adding insertion pattern: {e}"

        label = "deletions" if length < 0 else f"{length}-base insertions"
        return {
            'length': length,
            'spacing': spacing,
            'total_added': total_added,
            'per_helix': per_helix,
            'message': f"Added {total_added} {label} across {len(per_helix)} helices"
        }

    def listInsertions(self, helix_num=None, strand_type=None):
        """
        List all insertions/deletions in the design or on a specific helix.

        Args:
            helix_num (int, optional): Filter to a specific helix
            strand_type (str, optional): Filter to "scaffold" or "staple"

        Returns:
            dict or str: List of insertions with helix_num, idx, length
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        vhs = part.getVirtualHelices()
        insertions = []

        for vh in vhs:
            vh_num = vh.number()
            if helix_num is not None and vh_num != helix_num:
                continue

            strand_sets = []
            if strand_type is None or strand_type.lower() == "scaffold":
                strand_sets.append(("scaffold", vh.scaffoldStrandSet()))
            if strand_type is None or strand_type.lower() == "staple":
                strand_sets.append(("staple", vh.stapleStrandSet()))

            for stype, ss in strand_sets:
                for strand in ss:
                    for ins in strand.insertionsOnStrand():
                        insertions.append({
                            'helix_num': vh_num,
                            'idx': ins.idx(),
                            'length': ins.length(),
                            'strand_type': stype
                        })

        insertions.sort(key=lambda x: (x['helix_num'], x['idx']))

        filter_desc = ""
        if helix_num is not None:
            filter_desc += f" on helix {helix_num}"
        if strand_type is not None:
            filter_desc += f" ({strand_type})"

        return {
            'count': len(insertions),
            'insertions': insertions,
            'message': f"Found {len(insertions)} insertions{filter_desc}"
        }

    def planScaffoldRouting(self, strand_type="scaffold"):
        """
        Plan and execute a complete scaffold routing for a 2×N grid design.

        Creates a single closed loop visiting all helices using half-crossovers,
        then removes exposed strand fragments. Everything is wrapped in one undo
        macro for atomic undo.

        Algorithm:
          - Detects 2×N grid topology from current design helices
          - Builds a serpentine path: top row L→R, cross, bottom row R→L, close
          - For each turn picks the crossover position matching the helix parity:
              * Even parity (scaffold L→R, exits HIGH end): pick highest valid position
              * Odd parity  (scaffold R→L, exits LOW end):  pick lowest valid position
          - Creates all planned half-crossovers
          - Deletes exposed dangling fragments

        Args:
            strand_type (str): "scaffold" or "staple" (default "scaffold")

        Returns:
            dict with 'path', 'crossovers', 'fragments_deleted', 'description'
            or {'error': ...} if the layout is unsupported
        """
        part = self.activePart
        if part is None:
            return {"error": "No active part"}

        st = StrandType.Scaffold if strand_type.lower() == "scaffold" \
            else StrandType.Staple
        get_ss = (lambda vh: vh.scaffoldStrandSet()) \
            if strand_type.lower() == "scaffold" \
            else (lambda vh: vh.stapleStrandSet())

        vhs = list(part.getVirtualHelices())
        if not vhs:
            return {"error": "No helices in design. Call createHelicesWithStrands first."}

        # Build neighbor graph from cadnano's own crossover geometry —
        # do NOT use row/col coordinates to infer topology.
        vh_set = set(vhs)
        adj = {vh: [] for vh in vhs}
        for vh in vhs:
            for neighbor_vh, idx, sType, isLowIdx in part.potentialCrossoverList(vh):
                if (sType == st and neighbor_vh is not None
                        and neighbor_vh in vh_set
                        and neighbor_vh not in adj[vh]):
                    adj[vh].append(neighbor_vh)

        # ── 2-helix special case ─────────────────────────────────────────────
        if len(vhs) == 2:
            vh_a, vh_b = vhs[0], vhs[1]
            if vh_b not in adj[vh_a]:
                return {
                    "error": (
                        f"H{vh_a.number()} and H{vh_b.number()} are not neighbors "
                        f"(no valid {strand_type} crossover positions between them)."
                    )
                }
            path = [vh_a, vh_b]
            n_cols = 1

        # ── 2×N grid: detect from neighbor graph, not row coordinates ────────
        else:
            # Partition helices into two "sides" using a BFS 2-colouring of the
            # neighbour graph.  In a 2×N honeycomb bundle every helix has exactly
            # one "across" neighbour (the other side) and at most one "along"
            # neighbour (the next column on the same side).
            # We detect "across" pairs as those whose neighbour lists contain each
            # other AND whose mutual neighbour count is exactly 2 (or boundary 1).
            # Simpler heuristic: 2-colour by BFS; if the graph is bipartite with
            # two equal-size colour classes → valid 2×N grid.
            color = {}
            queue = [vhs[0]]
            color[vhs[0]] = 0
            while queue:
                cur = queue.pop()
                for nb in adj[cur]:
                    if nb not in color:
                        color[nb] = 1 - color[cur]
                        queue.append(nb)
                    elif color[nb] == color[cur]:
                        return {
                            "error": (
                                "planScaffoldRouting requires a 2×N grid topology "
                                "(bipartite neighbour graph). This design has an "
                                "odd cycle in the neighbour graph. Use "
                                "addCrossoversForPair for non-standard layouts."
                            )
                        }

            side0 = sorted([v for v in vhs if color.get(v, 0) == 0], key=lambda v: v.coord()[1])
            side1 = sorted([v for v in vhs if color.get(v, 0) == 1], key=lambda v: v.coord()[1])

            if len(side0) != len(side1):
                return {
                    "error": (
                        f"Unequal helix counts on each side: "
                        f"{len(side0)} vs {len(side1)}. Cannot form a closed loop."
                    )
                }

            n_cols = len(side0)
            # Serpentine: side0 L→R, then side1 R→L
            path = side0 + list(reversed(side1))

        num_vhs = len(path)

        def is_even_parity(vh):
            row, col = vh.coord()
            return (row % 2) == (col % 2)

        def get_valid_positions(vh_a, vh_b):
            """Valid crossover indices between vh_a and vh_b where strands exist."""
            xovers = part.potentialCrossoverList(vh_a)
            positions = []
            for neighborVh, idx, sType, isLowIdx in xovers:
                if sType != st or neighborVh is None or neighborVh != vh_b:
                    continue
                # Only include positions where strands actually reach
                if (get_ss(vh_a).getStrand(idx) is not None and
                        get_ss(vh_b).getStrand(idx) is not None):
                    positions.append(idx)
            return sorted(positions)

        # Plan the crossovers before touching the undo stack
        planned = []   # list of (idx, vh_a, vh_b)
        for i in range(num_vhs):
            vh_a = path[i]
            vh_b = path[(i + 1) % num_vhs]

            positions = get_valid_positions(vh_a, vh_b)
            if not positions:
                return {
                    "error": (
                        f"No valid {strand_type} crossover positions between "
                        f"H{vh_a.number()} and H{vh_b.number()}. "
                        f"These helices may not be neighbors, or strands may be missing. "
                        f"Ensure createHelicesWithStrands was called first."
                    )
                }

            # Even parity (scaffold L→R, exits HIGH end) → use highest valid position
            # Odd parity  (scaffold R→L, exits LOW end)  → use lowest valid position
            idx = max(positions) if is_even_parity(vh_a) else min(positions)
            planned.append((idx, vh_a, vh_b))

        # Execute atomically
        part.undoStack().beginMacro(
            f"Plan {strand_type.capitalize()} Routing ({num_vhs} helices)"
        )
        try:
            created = []
            for idx, vh_a, vh_b in planned:
                s_a = get_ss(vh_a).getStrand(idx)
                s_b = get_ss(vh_b).getStrand(idx)
                if s_a is None:
                    part.undoStack().endMacro()
                    part.undoStack().undo()
                    return {"error": f"No {strand_type} strand at H{vh_a.number()} idx {idx}"}
                if s_b is None:
                    part.undoStack().endMacro()
                    part.undoStack().undo()
                    return {"error": f"No {strand_type} strand at H{vh_b.number()} idx {idx}"}
                # Skip if crossover already exists at this endpoint
                lo_a, hi_a = s_a.idxs()
                already = ((idx == lo_a and s_a.connectionLow() is not None) or
                           (idx == hi_a and s_a.connectionHigh() is not None))
                if already:
                    continue
                part.createXover(s_b, idx, s_a, idx, useUndoStack=True)
                created.append({
                    "helix1": vh_a.number(), "idx1": idx,
                    "helix2": vh_b.number(), "idx2": idx,
                    "strand_type": strand_type
                })

            # Delete exposed fragments inside the same macro
            dangling = []
            for vh in part.getVirtualHelices():
                for strand in list(get_ss(vh)):
                    if strand.connection5p() is None or strand.connection3p() is None:
                        dangling.append((vh.number(), strand))

            deleted = 0
            for vh_num, strand in dangling:
                vh = part.virtualHelix(vh_num)
                if vh is None:
                    continue
                ss = get_ss(vh)
                try:
                    conn3p = strand.connection3p()
                    if conn3p is not None:
                        part.removeXover(strand, conn3p, useUndoStack=True)
                    conn5p = strand.connection5p()
                    if conn5p is not None:
                        part.removeXover(conn5p, strand, useUndoStack=True)
                    ss.removeStrand(strand, useUndoStack=True)
                    deleted += 1
                except Exception:
                    pass  # already removed as side-effect of another deletion

            part.undoStack().endMacro()

        except Exception as e:
            part.undoStack().endMacro()
            part.undoStack().undo()
            return {"error": f"Error creating {strand_type} routing: {e}"}

        path_nums = [vh.number() for vh in path]
        return {
            "path": path_nums,
            "crossovers": created,
            "fragments_deleted": deleted,
            "description": (
                f"Routed {num_vhs}-helix ({n_cols}×2) {strand_type} as a single "
                f"closed loop. "
                f"Path: {' → '.join(str(h) for h in path_nums + [path_nums[0]])}. "
                f"{len(created)} half-crossovers created, "
                f"{deleted} exposed fragment(s) removed."
            )
        }

    def deleteExposedFragments(self, strand_type="scaffold"):
        """
        Delete strand segments that have an exposed (unconnected) 5' or 3' end.

        After createHelicesWithStrands + crossover placement, short fragments
        remain outside the crossover region at each end of every helix.  These
        have no biological meaning and must be removed so the scaffold (or
        staple) forms a clean closed loop with no free ends.

        Call this once after all crossovers for a routing are placed.  The
        entire deletion is wrapped in one undo macro.

        Args:
            strand_type (str): "scaffold" or "staple"

        Returns:
            str: Report of how many fragments were deleted.
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        stype = strand_type.lower()
        get_ss = (lambda vh: vh.scaffoldStrandSet()) if stype == "scaffold" \
            else (lambda vh: vh.stapleStrandSet())

        # Snapshot first — deletions change the strand sets in place
        dangling = []
        for vh in part.getVirtualHelices():
            for strand in list(get_ss(vh)):
                if strand.connection5p() is None or strand.connection3p() is None:
                    dangling.append((vh.number(), strand))

        if not dangling:
            return f"No exposed {strand_type} fragments found — design is clean."

        part.undoStack().beginMacro(
            f"Delete {len(dangling)} exposed {strand_type} fragment(s)"
        )
        deleted = 0
        for vh_num, strand in dangling:
            vh = part.virtualHelix(vh_num)
            if vh is None:
                continue
            ss = get_ss(vh)
            try:
                conn3p = strand.connection3p()
                if conn3p is not None:
                    part.removeXover(strand, conn3p, useUndoStack=True)
                conn5p = strand.connection5p()
                if conn5p is not None:
                    part.removeXover(conn5p, strand, useUndoStack=True)
                ss.removeStrand(strand, useUndoStack=True)
                deleted += 1
            except Exception:
                pass  # already removed as a side-effect of another deletion
        part.undoStack().endMacro()

        return f"Deleted {deleted} exposed {strand_type} fragment(s). Design should now have no free ends."

    def deleteOrphanFragments(self, strand_type="scaffold"):
        """
        Delete strand segments that have BOTH their 5' and 3' termini exposed
        on the same helix — i.e. the strand has no crossover connections anywhere.

        This is the correct cleanup step after planScaffoldRouting().  After
        crossovers are placed at valid positions (e.g. index 5 and 68 on an
        84 bp helix), short edge fragments remain at positions 0-4 and 69-83.
        These fragments were never connected via crossover and should be removed.

        Contrast with deleteExposedFragments() which uses OR (deletes any strand
        with at least one free end) — that is too aggressive and would remove
        strands that are part of an incomplete but in-progress routing.

        Args:
            strand_type (str): "scaffold" or "staple"

        Returns:
            str: Report of how many orphan fragments were deleted.
        """
        part = self.activePart
        if part is None:
            return "Error: No active part"

        stype = strand_type.lower()
        get_ss = (lambda vh: vh.scaffoldStrandSet()) if stype == "scaffold" \
            else (lambda vh: vh.stapleStrandSet())

        # Only delete strands where BOTH ends are unconnected (AND, not OR)
        orphans = []
        for vh in part.getVirtualHelices():
            for strand in list(get_ss(vh)):
                if strand.connection5p() is None and strand.connection3p() is None:
                    orphans.append((vh.number(), strand))

        if not orphans:
            return (f"No orphan {strand_type} fragments found "
                    f"(strands with both ends unconnected).")

        part.undoStack().beginMacro(
            f"Delete {len(orphans)} orphan {strand_type} fragment(s)"
        )
        deleted = 0
        for vh_num, strand in orphans:
            vh = part.virtualHelix(vh_num)
            if vh is None:
                continue
            ss = get_ss(vh)
            try:
                ss.removeStrand(strand, useUndoStack=True)
                deleted += 1
            except Exception:
                pass  # already removed as side-effect
        part.undoStack().endMacro()

        return (f"Deleted {deleted} orphan {strand_type} fragment(s) "
                f"(both ends unconnected — edge fragments outside crossover region).")

    # ==================== VERIFICATION METHODS ====================

    def verifyDesign(self):
        """
        Verify the current design and get feedback.

        Returns:
            str: Verification results with score and issues
        """
        verifier = DesignVerifier(self._documentController)
        result = verifier.verifyDesign()

        # Check for exposed 5'/3' ends — fragments left over from crossover placement
        part = self.activePart
        exposed_issues = []
        if part is not None:
            for stype_label, get_ss in [
                ("scaffold", lambda vh: vh.scaffoldStrandSet()),
                ("staple",   lambda vh: vh.stapleStrandSet()),
            ]:
                exposed = []
                for vh in part.getVirtualHelices():
                    for strand in get_ss(vh):
                        if strand.connectionLow() is None or strand.connectionHigh() is None:
                            lo, hi = strand.idxs()
                            exposed.append(f"H{vh.number()}[{lo}-{hi}]")
                if exposed:
                    exposed_issues.append(
                        f"{len(exposed)} exposed {stype_label} fragment(s) with free ends: "
                        + ", ".join(exposed[:5])
                        + (" …" if len(exposed) > 5 else "")
                        + " — call deleteExposedFragments() to remove"
                    )

        if exposed_issues:
            result['issues'] = result.get('issues', []) + exposed_issues
            result['valid'] = False

        output = [f"Design Score: {result['score']:.2f}/1.00"]

        if result['valid']:
            output.append("Status: VALID")
        else:
            output.append("Status: INVALID")

        if result.get('issues'):
            output.append("Issues:")
            for issue in result['issues']:
                output.append(f"  - {issue}")

        if result.get('warnings'):
            output.append("Warnings:")
            for warning in result['warnings']:
                output.append(f"  - {warning}")

        metrics = result.get('metrics', {})
        if metrics:
            output.append(f"Metrics: helices={metrics.get('helix_count', 0)}, " +
                         f"scaffold_oligos={metrics.get('scaffold_oligo_count', 0)}, " +
                         f"staple_oligos={metrics.get('staple_oligo_count', 0)}")

        return '\n'.join(output)

    def verifyScaffoldRouting(self):
        """
        Verify scaffold routing: checks for a single closed loop with no exposed termini.

        Two independent checks (both must pass for reward=1.0):
          1. verifyNoScaffoldTermini  — no strand has a free 5' or 3' end (O(strands))
          2. verifyScaffoldClosedLoop — scaffold oligos form exactly one closed loop

        These checks are valid RLVR reward signals:
          - reward=1.0  → scaffold is a single closed loop, trajectory succeeded
          - reward=0.5  → multiple closed loops, partial credit (missing crossovers)
          - reward=0.0  → exposed termini, trajectory failed

        Returns:
            str: Human-readable result with reward score
        """
        verifier = DesignVerifier(self._documentController)
        signal = verifier.getRewardSignal(structure_type='scaffold_routing')

        lines = [
            f"Scaffold routing verification (reward={signal['reward']:.2f}):",
            f"  Closed loop: {signal['breakdown']['closed_loop']['message']}",
            f"  No termini:  {signal['breakdown']['no_termini']['message']}",
        ]

        if signal['breakdown']['no_termini']['exposed_ends']:
            for e in signal['breakdown']['no_termini']['exposed_ends'][:5]:
                lines.append(f"    H{e['helix']} [{e['low']}-{e['high']}] "
                             f"free_5p={e['free_5p']} free_3p={e['free_3p']}")
            rem = len(signal['breakdown']['no_termini']['exposed_ends']) - 5
            if rem > 0:
                lines.append(f"    ... and {rem} more")

        lines.append(f"PASSED" if signal['valid'] else "FAILED")
        return '\n'.join(lines)

    def verify6HelixBundle(self):
        """
        Verify the design as a 6-helix bundle.

        Returns:
            str: Detailed verification results
        """
        verifier = DesignVerifier(self._documentController)
        result = verifier.verify6HelixBundle()

        output = [f"6-Helix Bundle Score: {result['score']:.2f}/1.00"]

        if result['valid']:
            output.append("Status: VALID 6-HELIX BUNDLE")
        else:
            output.append("Status: INVALID")

        if result.get('issues'):
            output.append("Issues:")
            for issue in result['issues']:
                output.append(f"  - {issue}")

        if result.get('warnings'):
            output.append("Warnings:")
            for warning in result['warnings']:
                output.append(f"  - {warning}")

        metrics = result.get('metrics', {})
        output.append(f"Helices: {metrics.get('helix_count', 0)}/6")
        output.append(f"Helices with scaffold: {metrics.get('helices_with_scaffold', 0)}/6")
        output.append(f"Scaffold crossover pairs: {metrics.get('scaffold_crossover_pairs', 0)}/5 minimum")
        output.append(f"Scaffold oligos: {metrics.get('scaffold_oligo_count', 0)} (should be 1)")

        return '\n'.join(output)

    def getValidCrossoverPositions(self, helix1, helix2, strand_type):
        """
        Get valid crossover positions between two helices.
        Delegates to the model's potentialCrossoverList().

        Args:
            helix1 (int): First helix number
            helix2 (int): Second helix number
            strand_type (str): "scaffold" or "staple"

        Returns:
            str: List of valid crossover indices
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

        st = StrandType.Scaffold if strand_type.lower() == "scaffold" else StrandType.Staple
        crossovers = part.potentialCrossoverList(vh1)

        valid_indices = sorted(set(
            idx for neighborVh, idx, sType, isLowIdx in crossovers
            if sType == st and neighborVh == vh2
        ))

        return f"Valid {strand_type} crossover indices between helix {helix1} and {helix2}: {valid_indices}"

    # ==================== TRAINING DATA EXTRACTION ====================

    def extractTrajectoryFromJSON(self, json_path, task=""):
        """
        Extract a trajectory (sequence of method calls) from a cadnano JSON file.
        Converts an expert design into an action sequence suitable for training data.

        The JSON is parsed to find:
        - Helix positions (row, col)
        - Which strand types are used (scaffold, staple)
        - All half-crossovers (the inter-helix connections)

        Returns a dict with 'actions' (list of [method, params]) and metadata.
        The actions recreate the design from scratch when executed in order.

        Args:
            json_path (str): Path to the cadnano JSON file (can use ~ for home)
            task (str): Natural-language description of what this design accomplishes

        Returns:
            dict or str: Trajectory dict or error string
        """
        import json as _json
        import os

        json_path = os.path.expanduser(json_path)
        try:
            with open(json_path) as f:
                data = _json.load(f)
        except Exception as e:
            return f"Error reading {json_path}: {e}"

        vstrands = data.get('vstrands', [])
        if not vstrands:
            return "Error: No vstrands found in JSON"

        part_size = len(vstrands[0]['scaf'])
        positions = [[vs['row'], vs['col']] for vs in sorted(vstrands, key=lambda v: v['num'])]

        def _has_content(strand_data):
            return any(any(x != -1 for x in s) for s in strand_data)

        has_scaf = any(_has_content(vs['scaf']) for vs in vstrands)
        has_stap = any(_has_content(vs['stap']) for vs in vstrands)

        actions = []

        # Step 1: create helices with full-length strands
        for stype in ([('scaffold')] if has_scaf else []) + ([('staple')] if has_stap else []):
            if isinstance(stype, tuple):
                stype = stype[0]
            actions.append(['createHelicesWithStrands', {
                'positions': positions,
                'strand_type': stype,
                'length': part_size - 1
            }])

        # Step 2: extract half-crossovers and add them in position order.
        # We only record each crossover once (from the helix with the lower number,
        # or from the helix where the outgoing index is lower — to get a stable order).
        for stype, key in [('scaffold', 'scaf'), ('staple', 'stap')]:
            if (stype == 'scaffold' and not has_scaf) or (stype == 'staple' and not has_stap):
                continue

            seen = set()
            xovers = []
            for vs in vstrands:
                num = vs['num']
                for i, s in enumerate(vs[key]):
                    _, _, next_vh, next_idx = s
                    if next_vh in (-1, num):
                        continue
                    # Canonical key: sorted pair so we don't double-add
                    canon = tuple(sorted([(num, i), (next_vh, next_idx)]))
                    if canon in seen:
                        continue
                    seen.add(canon)
                    xovers.append({
                        'helix1': num, 'idx1': i,
                        'helix2': next_vh, 'idx2': next_idx,
                        'sort_idx': min(i, next_idx)
                    })

            # Sort by position so crossovers are added low-to-high
            xovers.sort(key=lambda x: x['sort_idx'])
            for xo in xovers:
                actions.append(['createHalfCrossover', {
                    'helix1': xo['helix1'], 'idx1': xo['idx1'],
                    'helix2': xo['helix2'], 'idx2': xo['idx2'],
                    'strand_type': stype
                }])

        n_xovers = sum(1 for a in actions if a[0] == 'createHalfCrossover')
        return {
            'source_file': json_path,
            'task': task or f'Recreate design from {os.path.basename(json_path)}',
            'part_size': part_size,
            'helix_count': len(vstrands),
            'strand_types': (['scaffold'] if has_scaf else []) + (['staple'] if has_stap else []),
            'crossover_count': n_xovers,
            'action_count': len(actions),
            'actions': actions
        }

    def exportTrainingExample(self, json_path, task="", output_path=""):
        """
        Export a training example in JSONL format for SFT fine-tuning.

        Parses the expert JSON, extracts the action trajectory, and writes a
        conversation record in the OpenAI messages format (compatible with
        Unsloth / LlamaFactory fine-tuning pipelines).

        Each action becomes an assistant tool_call followed by a tool result.
        The conversation structure mirrors what the Claude API backend produces
        during a real agent session, so the same data format works for both
        SFT on expert examples and SFT on collected Claude trajectories.

        Args:
            json_path (str): Path to expert cadnano JSON
            task (str): Natural-language task description (shown as user message)
            output_path (str): JSONL file to append to. If empty, returns the JSON string.

        Returns:
            str: Success message or the JSONL string if output_path is empty
        """
        import json as _json
        import os

        traj = self.extractTrajectoryFromJSON(json_path, task)
        if isinstance(traj, str):
            return traj

        messages = [
            {"role": "system", "content": (
                "You are a cadnano DNA nanostructure design assistant. "
                "Use the provided tools to build the requested design."
            )},
            {"role": "user", "content": traj['task']}
        ]

        for method_name, params in traj['actions']:
            # Assistant tool call
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "type": "function",
                    "id": f"call_{method_name}_{params.get('helix1','')}{params.get('idx1','')}",
                    "function": {
                        "name": method_name,
                        "arguments": _json.dumps(params)
                    }
                }]
            })
            # Simulated tool result (success — real trajectories have actual results)
            messages.append({
                "role": "tool",
                "content": f"Success"
            })

        messages.append({
            "role": "assistant",
            "content": (
                f"Done. Created a {traj['helix_count']}-helix design with "
                f"{traj['crossover_count']} crossovers from {os.path.basename(json_path)}."
            )
        })

        record = {
            "messages": messages,
            "metadata": {
                "source": json_path,
                "helix_count": traj['helix_count'],
                "action_count": traj['action_count'],
                "crossover_count": traj['crossover_count'],
                "part_size": traj['part_size']
            }
        }

        json_str = _json.dumps(record)
        if output_path:
            output_path = os.path.expanduser(output_path)
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, 'a') as f:
                f.write(json_str + '\n')
            return f"Appended training example to {output_path} ({traj['action_count']} actions)"
        return json_str
