"""
agentverifier.py

Verification layer for agent actions and DNA nanostructure designs.
Provides validation and reward signals for RLVR-style training.
"""

from cadnano2.model.enum import StrandType
from cadnano2.model.parts.honeycombpart import Crossovers, HoneycombPart


def _buildXoverPositionMap(scafLow, scafHigh, stapLow, stapHigh):
    """Build crossover position lookup dicts from the model's Crossovers tables."""
    scaffold = {}
    staple = {}
    for i in range(len(scafLow)):
        direction = f'p{i}'
        scaffold[direction] = sorted(scafLow[i] + scafHigh[i])
        staple[direction] = sorted(stapLow[i] + stapHigh[i])
    return scaffold, staple


# Derived from the canonical Crossovers tables — single source of truth
SCAFFOLD_XOVER_POSITIONS, STAPLE_XOVER_POSITIONS = _buildXoverPositionMap(
    Crossovers.honeycombScafLow, Crossovers.honeycombScafHigh,
    Crossovers.honeycombStapLow, Crossovers.honeycombStapHigh,
)


class DesignVerifier:
    """
    Verifies DNA nanostructure designs and agent actions.

    Provides:
    - Pre-execution validation (can this action succeed?)
    - Post-execution validation (is the design correct?)
    - Reward signals for reinforcement learning
    """

    STEP = HoneycombPart._step

    def __init__(self, documentController):
        self._documentController = documentController

    @property
    def activePart(self):
        return self._documentController.activePart()

    # ==================== PRE-EXECUTION VALIDATION ====================

    def validateAction(self, methodName, params):
        """
        Validate an action before execution.

        Args:
            methodName (str): Method to be called
            params (dict): Parameters for the method

        Returns:
            tuple: (is_valid: bool, message: str, suggestions: list)
        """
        validator = getattr(self, f'_validate_{methodName}', None)
        if validator:
            return validator(params)
        return True, "No validation rules for this method", []

    def _validate_createHelix(self, params):
        """Validate helix creation."""
        row = params.get('row')
        col = params.get('col')

        if row is None or col is None:
            return False, "Missing row or col parameter", []

        part = self.activePart
        if part is None:
            return False, "No active part - create a Honeycomb part first", []

        # Check if position is already occupied
        existing = part.virtualHelixAtCoord((row, col))
        if existing:
            return False, f"Position ({row}, {col}) already has helix {existing.number()}", []

        # Check if position is within reasonable bounds
        if row < 0 or row > 50 or col < 0 or col > 50:
            return False, f"Position ({row}, {col}) is outside typical design area", []

        return True, "Valid helix position", []

    def _validate_extendPartSize(self, params):
        """Validate part size extension."""
        min_length = params.get('min_length_needed')

        if min_length is None:
            return False, "Missing min_length_needed parameter", []

        if not isinstance(min_length, int) or min_length <= 0:
            return False, "min_length_needed must be a positive integer", []

        part = self.activePart
        if part is None:
            return False, "No active part - create a Honeycomb part first", []

        if min_length > 10000:
            return False, f"Requested length {min_length} exceeds maximum (10000)", []

        current_max = part.maxBaseIdx()
        if min_length <= current_max + 1:
            return True, f"Part already large enough (current: 0-{current_max})", []

        return True, "Valid extension request", []

    def _validate_createScaffoldStrand(self, params):
        """Validate scaffold strand creation."""
        return self._validateStrandCreation(params, 'scaffold')

    def _validate_createStapleStrand(self, params):
        """Validate staple strand creation."""
        return self._validateStrandCreation(params, 'staple')

    def _validateStrandCreation(self, params, strand_type):
        """Common validation for strand creation."""
        helix_num = params.get('helix_num')
        start_idx = params.get('start_idx')
        length = params.get('length')

        if helix_num is None or start_idx is None or length is None:
            return False, "Missing required parameters", []

        part = self.activePart
        if part is None:
            return False, "No active part", []

        vh = part.virtualHelix(helix_num)
        if vh is None:
            return False, f"Helix {helix_num} does not exist", []

        end_idx = start_idx + length - 1
        max_idx = part.maxBaseIdx()

        if start_idx < 0 or end_idx > max_idx:
            return False, f"Strand extends beyond valid range (0-{max_idx}). Use extendPartSize({length}) first.", [
                f"Call extendPartSize with min_length_needed={length} to extend the part"
            ]

        # Check alignment to step size for typical designs
        if length % self.STEP != 0:
            suggestions = []
            aligned_length = (length // self.STEP) * self.STEP
            if aligned_length > 0:
                suggestions.append(f"Consider length={aligned_length} (aligned to {self.STEP}bp steps)")
            return True, f"Warning: length {length} not aligned to {self.STEP}bp step", suggestions

        return True, "Valid strand parameters", []

    def _validate_createCrossover(self, params):
        """Validate crossover creation."""
        helix1 = params.get('helix1')
        idx1 = params.get('idx1')
        helix2 = params.get('helix2')
        idx2 = params.get('idx2')
        strand_type = params.get('strand_type', 'scaffold')

        if any(p is None for p in [helix1, idx1, helix2, idx2]):
            return False, "Missing required parameters", []

        part = self.activePart
        if part is None:
            return False, "No active part", []

        vh1 = part.virtualHelix(helix1)
        vh2 = part.virtualHelix(helix2)

        if vh1 is None:
            return False, f"Helix {helix1} does not exist", []
        if vh2 is None:
            return False, f"Helix {helix2} does not exist", []

        # Check if helices are neighbors
        neighbors = part.getVirtualHelixNeighbors(vh1)
        if vh2 not in neighbors:
            neighbor_nums = [n.number() if n else None for n in neighbors]
            return False, f"Helix {helix2} is not a neighbor of helix {helix1}", [
                f"Valid neighbors: {neighbor_nums}"
            ]

        # Check crossover position alignment
        neighbor_idx = neighbors.index(vh2)
        direction = f'p{neighbor_idx}'

        if strand_type.lower() == 'scaffold':
            valid_positions = SCAFFOLD_XOVER_POSITIONS.get(direction, [])
        else:
            valid_positions = STAPLE_XOVER_POSITIONS.get(direction, [])

        idx_mod = idx1 % self.STEP
        if idx_mod not in valid_positions:
            return False, f"Index {idx1} (mod {self.STEP} = {idx_mod}) is not a valid {strand_type} crossover position", [
                f"Valid positions (mod {self.STEP}): {valid_positions}",
                f"Nearby valid indices: {[idx1 - idx_mod + p for p in valid_positions if idx1 - idx_mod + p >= 0]}"
            ]

        return True, "Valid crossover position", []

    # ==================== LEVEL 2 BATCH VALIDATION ====================

    def _validate_createHelicesWithStrands(self, params):
        """Validate batch helix+strand creation."""
        positions = params.get('positions')
        strand_type = params.get('strand_type')
        length = params.get('length')

        if positions is None or strand_type is None or length is None:
            return False, "Missing required parameters (positions, strand_type, length)", []

        if not isinstance(positions, list) or len(positions) == 0:
            return False, "positions must be a non-empty list of [row, col] pairs", []

        if strand_type.lower() not in ('scaffold', 'staple', 'both'):
            return False, "strand_type must be 'scaffold', 'staple', or 'both'", []

        if not isinstance(length, int) or length <= 0:
            return False, "length must be a positive integer", []

        if length > 10000:
            return False, f"Requested length {length} exceeds maximum (10000)", []

        part = self.activePart
        if part is None:
            return False, "No active part", []

        suggestions = []

        # Check positions are valid honeycomb coordinates
        for pos in positions:
            if not isinstance(pos, (list, tuple)) or len(pos) != 2:
                return False, f"Invalid position format: {pos}. Expected [row, col]", []
            row, col = pos[0], pos[1]
            if row < 0 or row > 50 or col < 0 or col > 50:
                return False, f"Position ({row}, {col}) is outside typical design area", []
            existing = part.virtualHelixAtCoord((row, col))
            if existing:
                return False, f"Position ({row}, {col}) already has helix {existing.number()}", []

        # Warn if length is not a multiple of step size
        if length % self.STEP != 0:
            aligned = (length // self.STEP) * self.STEP
            suggestions.append(f"Consider length={aligned} (aligned to {self.STEP}bp steps)")
            return True, f"Warning: length {length} not aligned to {self.STEP}bp step", suggestions

        return True, "Valid batch helix creation", suggestions

    def _validate_addCrossoversForPair(self, params):
        """Validate batch crossover creation between a pair."""
        helix1 = params.get('helix1')
        helix2 = params.get('helix2')
        strand_type = params.get('strand_type')

        if helix1 is None or helix2 is None or strand_type is None:
            return False, "Missing required parameters (helix1, helix2, strand_type)", []

        part = self.activePart
        if part is None:
            return False, "No active part", []

        vh1 = part.virtualHelix(helix1)
        vh2 = part.virtualHelix(helix2)

        if vh1 is None:
            return False, f"Helix {helix1} does not exist", []
        if vh2 is None:
            return False, f"Helix {helix2} does not exist", []

        neighbors = part.getVirtualHelixNeighbors(vh1)
        if vh2 not in neighbors:
            neighbor_nums = [n.number() if n else None for n in neighbors]
            return False, f"Helix {helix2} is not a neighbor of helix {helix1}", [
                f"Valid neighbors: {neighbor_nums}"
            ]

        return True, "Valid crossover pair", []

    def _validate_addAllNeighborCrossovers(self, params):
        """Validate bulk crossover creation."""
        strand_type = params.get('strand_type')
        if strand_type is None:
            return False, "Missing required parameter: strand_type", []

        part = self.activePart
        if part is None:
            return False, "No active part", []

        vhs = part.getVirtualHelices()
        if len(vhs) < 2:
            return False, "Need at least 2 helices to create crossovers", []

        return True, "Valid bulk crossover request", []

    def _validate_resizeAllStrands(self, params):
        """Validate bulk strand resize."""
        strand_type = params.get('strand_type')
        new_length = params.get('new_length')
        delta = params.get('delta')

        if strand_type is None:
            return False, "Missing required parameter: strand_type", []

        if new_length is None and delta is None:
            return False, "Provide either new_length or delta", []

        if new_length is not None and new_length <= 0:
            return False, "new_length must be a positive integer", []

        part = self.activePart
        if part is None:
            return False, "No active part", []

        if new_length is not None and new_length - 1 > part.maxBaseIdx():
            return False, (f"new_length {new_length} exceeds part size "
                          f"(max index {part.maxBaseIdx()}). "
                          f"Extend part size first."), [
                f"Call extendPartSize with min_length_needed={new_length}"
            ]

        return True, "Valid bulk resize request", []

    # ==================== DESIGN VERIFICATION ====================

    def verifyDesign(self):
        """
        Verify the overall design quality.

        Returns:
            dict: Verification results with scores and issues
        """
        part = self.activePart
        if part is None:
            return {
                'valid': False,
                'score': 0.0,
                'issues': ['No active part'],
                'metrics': {}
            }

        issues = []
        warnings = []
        metrics = {}

        # Count helices
        vhs = part.getVirtualHelices()
        metrics['helix_count'] = len(vhs)

        if len(vhs) == 0:
            issues.append("No helices in design")
            return {
                'valid': False,
                'score': 0.0,
                'issues': issues,
                'metrics': metrics
            }

        # Check each helix
        helices_with_scaffold = 0
        helices_with_staple = 0
        total_scaffold_length = 0
        total_staple_length = 0
        crossover_count = 0

        for vh in vhs:
            scafSS = vh.scaffoldStrandSet()
            stapSS = vh.stapleStrandSet()

            scaf_strands = list(scafSS)
            stap_strands = list(stapSS)

            if scaf_strands:
                helices_with_scaffold += 1
                for strand in scaf_strands:
                    lo, hi = strand.idxs()
                    total_scaffold_length += hi - lo + 1

            if stap_strands:
                helices_with_staple += 1
                for strand in stap_strands:
                    lo, hi = strand.idxs()
                    total_staple_length += hi - lo + 1

        metrics['helices_with_scaffold'] = helices_with_scaffold
        metrics['helices_with_staple'] = helices_with_staple
        metrics['total_scaffold_length'] = total_scaffold_length
        metrics['total_staple_length'] = total_staple_length

        # Check for missing strands
        if helices_with_scaffold < len(vhs):
            issues.append(f"Only {helices_with_scaffold}/{len(vhs)} helices have scaffold strands")

        if helices_with_staple < len(vhs):
            warnings.append(f"Only {helices_with_staple}/{len(vhs)} helices have staple strands")

        # Count oligos (connected strand segments)
        scaffold_oligos = set()
        staple_oligos = set()
        for oligo in part.oligos():
            if oligo.isStaple():
                staple_oligos.add(oligo)
            else:
                scaffold_oligos.add(oligo)

        metrics['scaffold_oligo_count'] = len(scaffold_oligos)
        metrics['staple_oligo_count'] = len(staple_oligos)

        # For a proper bundle, scaffold should be 1 continuous oligo
        if len(scaffold_oligos) > 1:
            warnings.append(f"Scaffold is fragmented into {len(scaffold_oligos)} separate oligos (should be 1 for a connected bundle)")

        # Calculate score
        score = self._calculateScore(metrics, issues, warnings, len(vhs))

        return {
            'valid': len(issues) == 0,
            'score': score,
            'issues': issues,
            'warnings': warnings,
            'metrics': metrics
        }

    def verify6HelixBundle(self):
        """
        Verify a 6-helix bundle specifically.

        Returns:
            dict: Detailed verification results
        """
        base_result = self.verifyDesign()

        part = self.activePart
        if part is None:
            return base_result

        vhs = part.getVirtualHelices()
        issues = list(base_result.get('issues', []))
        warnings = list(base_result.get('warnings', []))
        metrics = dict(base_result.get('metrics', {}))

        # Check helix count
        if len(vhs) != 6:
            issues.append(f"Expected 6 helices, found {len(vhs)}")

        # Check helix arrangement (should form 2x3 or similar pattern)
        coords = [vh.coord() for vh in vhs]
        rows = set(c[0] for c in coords)
        cols = set(c[1] for c in coords)

        metrics['row_span'] = max(rows) - min(rows) + 1 if rows else 0
        metrics['col_span'] = max(cols) - min(cols) + 1 if cols else 0

        # Check connectivity via crossovers
        # A 6-helix bundle should have crossovers connecting adjacent helices
        connected_pairs = set()
        for vh in vhs:
            for strand in vh.scaffoldStrandSet():
                # Check 5' and 3' connections
                conn5 = strand.connection5p()
                conn3 = strand.connection3p()
                if conn5:
                    other_vh = conn5.virtualHelix()
                    if other_vh != vh:
                        pair = tuple(sorted([vh.number(), other_vh.number()]))
                        connected_pairs.add(pair)
                if conn3:
                    other_vh = conn3.virtualHelix()
                    if other_vh != vh:
                        pair = tuple(sorted([vh.number(), other_vh.number()]))
                        connected_pairs.add(pair)

        metrics['scaffold_crossover_pairs'] = len(connected_pairs)

        # A 6-helix bundle should have at least 5 pairs connected (to form one scaffold)
        if len(connected_pairs) < 5:
            warnings.append(f"Only {len(connected_pairs)} helix pairs connected by scaffold crossovers (need at least 5 for continuous scaffold)")

        # Recalculate score with 6-helix specific criteria
        score = self._calculate6HelixScore(metrics, issues, warnings)

        return {
            'valid': len(issues) == 0,
            'score': score,
            'issues': issues,
            'warnings': warnings,
            'metrics': metrics,
            'structure_type': '6-helix bundle'
        }

    def _calculateScore(self, metrics, issues, warnings, expected_helices):
        """Calculate a 0-1 score for the design."""
        if expected_helices == 0:
            return 0.0

        score = 1.0

        # Penalize for issues
        score -= len(issues) * 0.2

        # Small penalty for warnings
        score -= len(warnings) * 0.05

        # Reward for completeness
        helix_count = metrics.get('helix_count', 0)
        if helix_count >= expected_helices:
            score += 0.1

        # Reward for strand coverage
        if metrics.get('helices_with_scaffold', 0) == helix_count:
            score += 0.1

        # Reward for connected scaffold
        if metrics.get('scaffold_oligo_count', 0) == 1:
            score += 0.2

        return max(0.0, min(1.0, score))

    def _calculate6HelixScore(self, metrics, issues, warnings):
        """Calculate score specifically for 6-helix bundle."""
        score = 1.0

        # Must have exactly 6 helices
        helix_count = metrics.get('helix_count', 0)
        if helix_count != 6:
            score -= 0.3 * abs(helix_count - 6) / 6

        # All helices should have scaffold
        if metrics.get('helices_with_scaffold', 0) < 6:
            missing = 6 - metrics.get('helices_with_scaffold', 0)
            score -= 0.1 * missing

        # Scaffold should be one continuous oligo
        scaffold_oligos = metrics.get('scaffold_oligo_count', 0)
        if scaffold_oligos != 1:
            score -= 0.2 * min(scaffold_oligos - 1, 5) / 5

        # Should have crossover connections
        xover_pairs = metrics.get('scaffold_crossover_pairs', 0)
        if xover_pairs < 5:
            score -= 0.2 * (5 - xover_pairs) / 5

        # Penalize issues/warnings
        score -= len(issues) * 0.15
        score -= len(warnings) * 0.03

        return max(0.0, min(1.0, score))

    # ==================== REWARD SIGNAL FOR RLVR ====================

    def getRewardSignal(self, structure_type=None):
        """
        Get a reward signal for RLVR training.

        Args:
            structure_type (str): Optional specific structure to verify

        Returns:
            dict: Reward signal with score and breakdown
        """
        if structure_type == '6-helix':
            result = self.verify6HelixBundle()
        else:
            result = self.verifyDesign()

        return {
            'reward': result['score'],
            'valid': result['valid'],
            'breakdown': {
                'issues': result.get('issues', []),
                'warnings': result.get('warnings', []),
                'metrics': result.get('metrics', {})
            },
            'feedback': self._generateFeedback(result)
        }

    def _generateFeedback(self, result):
        """Generate human-readable feedback from verification result."""
        feedback = []

        score = result.get('score', 0)
        if score >= 0.9:
            feedback.append("Excellent! Design is well-formed.")
        elif score >= 0.7:
            feedback.append("Good design with minor issues.")
        elif score >= 0.5:
            feedback.append("Design has significant issues to address.")
        else:
            feedback.append("Design needs major corrections.")

        for issue in result.get('issues', []):
            feedback.append(f"Issue: {issue}")

        for warning in result.get('warnings', []):
            feedback.append(f"Warning: {warning}")

        return '\n'.join(feedback)
