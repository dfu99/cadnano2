"""
agenttools.py

Anthropic tool schema definitions for the Claude API backend.
These replace text-based JSON format instructions with structured tool use.
"""

TOOL_SCHEMAS = [
    # ==================== LEVEL 2 — QUERY TOOLS ====================

    {
        "name": "analyzeDesign",
        "description": (
            "Complete state dump of the current design — all helices, strands, "
            "crossovers, issues, and a quality score. Call this first if you don't "
            "know the current state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "describeHelix",
        "description": (
            "Rich single-call description of one helix: parity, directions, neighbors, "
            "strands present, and valid crossover positions. Use before adding crossovers "
            "to understand what's already there."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {
                    "type": "integer",
                    "description": "The virtual helix number to describe."
                }
            },
            "required": ["helix_num"]
        }
    },
    {
        "name": "getNeighborPairs",
        "description": (
            "Return all neighbor pairs in the design with direction labels. "
            "Use to understand the lattice topology before adding crossovers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "suggestCrossovers",
        "description": (
            "Return annotated crossover positions between two neighboring helices: "
            "which positions are occupied, available, recommended, whether each "
            "is an edge position (is_edge), and whether it is the parity-determined "
            "routing turn (is_routing_turn). Only the routing turn position should "
            "use a half-crossover for scaffold; all others use double crossovers. "
            "Also returns routing_turn_idx — the specific position for the half-crossover. "
            "Call inferScaffoldRoute() first for the full routing plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix1": {
                    "type": "integer",
                    "description": "First helix number."
                },
                "helix2": {
                    "type": "integer",
                    "description": "Second helix number (must be a neighbor of helix1)."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Whether to suggest crossovers for scaffold or staple strands."
                },
                "min_spacing": {
                    "type": "integer",
                    "description": "Minimum bp spacing between crossovers (optional, defaults to 7)."
                }
            },
            "required": ["helix1", "helix2", "strand_type"]
        }
    },

    {
        "name": "inferScaffoldRoute",
        "description": (
            "Infer the optimal scaffold routing path through the helix neighbor graph. "
            "Returns a Hamiltonian cycle (or path) with the turn position for each "
            "consecutive pair, determined by helix parity.\n\n"
            "Each turn entry specifies:\n"
            "- helix_from / helix_to: the pair in routing order\n"
            "- turn_idx: the crossover position where the scaffold turns (half-crossover)\n"
            "- exit_end: 'high (right)' for even parity, 'low (left)' for odd\n\n"
            "Also identifies non-routing neighbor pairs (these get only double crossovers "
            "for structural reinforcement, not routing half-crossovers).\n\n"
            "Call this BEFORE manually placing scaffold crossovers with addCrossoversForPair "
            "to know which positions should be half vs double crossovers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    # ==================== LEVEL 2 — BATCH EXECUTION TOOLS ====================

    {
        "name": "createHelicesWithStrands",
        "description": (
            "Create multiple helices with strands in one atomic operation. "
            "Auto-extends part size as needed. Preferred over creating helices one at a time.\n\n"
            "PREFERRED: pass num_helices (e.g. num_helices=6) and let the tool compute "
            "correct lattice positions automatically. Standard bundles supported: 1, 2, 3, 4, 6, 7, 19.\n\n"
            "ADVANCED: pass an explicit positions list of [row, col] pairs if you need a "
            "non-standard layout."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple", "both"],
                    "description": "Whether to create scaffold strands, staple strands, or both."
                },
                "length": {
                    "type": "integer",
                    "description": "Strand length in base pairs. Use multiples of 21 (e.g. 84, 126)."
                },
                "num_helices": {
                    "type": "integer",
                    "description": (
                        "Number of helices for a standard bundle (1, 2, 3, 4, 6, 7, 19). "
                        "Positions are computed automatically — no need to know the lattice coordinates. "
                        "Use this instead of positions whenever possible."
                    )
                },
                "positions": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2
                    },
                    "description": (
                        "Explicit list of [row, col] pairs for helix positions. "
                        "Only use this for non-standard layouts. "
                        "Prefer num_helices for standard bundle sizes."
                    )
                }
            },
            "required": ["strand_type", "length"]
        }
    },
    {
        "name": "addCrossoversForPair",
        "description": (
            "Add crossovers between two neighboring helices. "
            "Auto-computes valid positions if not specified. "
            "Each call is wrapped in one undo macro for atomic undo.\n\n"
            "ROUTING TURN: In 'auto' mode (default), exactly ONE scaffold crossover "
            "is created as a half-crossover — at the parity-determined routing turn "
            "(even parity → rightmost, odd parity → leftmost). All other positions "
            "and all staple crossovers use double crossovers. "
            "Call inferScaffoldRoute() first to see the full routing plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix1": {
                    "type": "integer",
                    "description": "First helix number."
                },
                "helix2": {
                    "type": "integer",
                    "description": "Second helix number (must be a neighbor of helix1)."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Whether to add scaffold or staple crossovers."
                },
                "positions": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Specific base pair positions for crossovers (optional)."
                },
                "spacing": {
                    "type": "integer",
                    "description": "Minimum spacing between auto-computed crossovers (optional)."
                },
                "crossover_type": {
                    "type": "string",
                    "enum": ["auto", "double", "half"],
                    "description": (
                        "Crossover type strategy. 'auto' (default): scaffold edges use "
                        "half-crossovers, interior and staple use double. 'double': always "
                        "double crossovers. 'half': always half-crossovers."
                    )
                }
            },
            "required": ["helix1", "helix2", "strand_type"]
        }
    },
    {
        "name": "addAllNeighborCrossovers",
        "description": (
            "Wire up all neighbor pairs in the design with crossovers. "
            "Wrapped in one undo macro. Use after createHelicesWithStrands "
            "to connect all helices.\n\n"
            "In 'auto' mode (default) for scaffold, infers a routing path "
            "(Hamiltonian cycle) and places exactly one half-crossover per "
            "routing turn. Non-routing neighbor pairs get only double crossovers. "
            "For staple, always uses double crossovers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Whether to add scaffold or staple crossovers."
                },
                "spacing": {
                    "type": "integer",
                    "description": "Minimum spacing between crossovers (optional)."
                },
                "crossover_type": {
                    "type": "string",
                    "enum": ["auto", "double", "half"],
                    "description": (
                        "Crossover type strategy. 'auto' (default): scaffold edges use "
                        "half-crossovers, interior and staple use double. 'double': always "
                        "double. 'half': always half."
                    )
                }
            },
            "required": ["strand_type"]
        }
    },
    {
        "name": "resizeAllStrands",
        "description": (
            "Resize strands in bulk. Respects parity for which end to resize. "
            "Use new_length to set an absolute length, or delta to adjust by a relative amount."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type to resize."
                },
                "new_length": {
                    "type": "integer",
                    "description": "New absolute length in bp (optional, use instead of delta)."
                },
                "delta": {
                    "type": "integer",
                    "description": "Change in length (positive to extend, negative to shrink). Optional."
                },
                "helix_num": {
                    "type": "integer",
                    "description": "If specified, only resize strands on this helix (optional)."
                }
            },
            "required": ["strand_type"]
        }
    },

    {
        "name": "removeCrossoversForPair",
        "description": (
            "Remove all crossovers between two helices for a given strand type. "
            "Wrapped in one undo macro for atomic undo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix1": {
                    "type": "integer",
                    "description": "First helix number."
                },
                "helix2": {
                    "type": "integer",
                    "description": "Second helix number."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type's crossovers to remove."
                }
            },
            "required": ["helix1", "helix2", "strand_type"]
        }
    },
    {
        "name": "removeAllCrossovers",
        "description": (
            "Remove all crossovers of a given strand type from the entire design. "
            "Wrapped in one undo macro for atomic undo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type's crossovers to remove."
                }
            },
            "required": ["strand_type"]
        }
    },
    {
        "name": "addInsertionPattern",
        "description": (
            "Add insertions or deletions at regular intervals along a helix. "
            "Skips positions where no strand exists or where a crossover is present. "
            "Wrapped in one undo macro for atomic undo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {
                    "type": "integer",
                    "description": "Which helix to add insertions on."
                },
                "length": {
                    "type": "integer",
                    "description": "Insertion length (positive) or -1 for deletion."
                },
                "spacing": {
                    "type": "integer",
                    "description": "Interval between insertions in base pairs (optional, default 21)."
                },
                "start_idx": {
                    "type": "integer",
                    "description": "Starting index (optional, defaults to first strand start)."
                },
                "end_idx": {
                    "type": "integer",
                    "description": "Ending index (optional, defaults to last strand end)."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type to target (optional, defaults to whichever exists)."
                }
            },
            "required": ["helix_num", "length"]
        }
    },
    {
        "name": "removeInsertionPattern",
        "description": (
            "Remove ALL insertions and deletions from a helix. "
            "Wrapped in one undo macro for atomic undo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {
                    "type": "integer",
                    "description": "Which helix to remove insertions from."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type (optional, defaults to both)."
                }
            },
            "required": ["helix_num"]
        }
    },
    {
        "name": "addInsertionPatternAll",
        "description": (
            "Add insertions or deletions across ALL helices in the design at regular intervals. "
            "Skips crossover positions. Wrapped in one undo macro for atomic undo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "length": {
                    "type": "integer",
                    "description": "Insertion length (positive) or -1 for deletion."
                },
                "spacing": {
                    "type": "integer",
                    "description": "Interval between insertions in base pairs (optional, default 21)."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type to target (optional, defaults to whichever exists)."
                }
            },
            "required": ["length"]
        }
    },
    {
        "name": "listInsertions",
        "description": (
            "List all insertions and deletions in the design, optionally filtered "
            "by helix number and/or strand type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {
                    "type": "integer",
                    "description": "Filter to a specific helix (optional)."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Filter by strand type (optional)."
                }
            },
            "required": []
        }
    },

    {
        "name": "autoBreakStaples",
        "description": (
            "Auto-break staple strands using cadnano's built-in Dijkstra-based "
            "algorithm. Finds optimal break positions to produce staples near "
            "the target length. Uses graph-based optimization for best results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_staple_len": {
                    "type": "integer",
                    "description": "Minimum staple length (default 30)."
                },
                "max_staple_len": {
                    "type": "integer",
                    "description": "Maximum staple length (default 40)."
                },
                "tgt_staple_len": {
                    "type": "integer",
                    "description": "Target staple length (default 35)."
                },
                "min_leg_len": {
                    "type": "integer",
                    "description": "Minimum bases after a crossover (default 3)."
                }
            },
            "required": []
        }
    },
    {
        "name": "splitStrandAt",
        "description": (
            "Split a strand at a specific index. Creates two strands from one. "
            "The split creates strands [..., idx] and [idx+1, ...]. "
            "Cannot split at strand endpoints."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {
                    "type": "integer",
                    "description": "Helix number."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type to split."
                },
                "idx": {
                    "type": "integer",
                    "description": "Index at which to split."
                }
            },
            "required": ["helix_num", "strand_type", "idx"]
        }
    },
    {
        "name": "breakStaplePattern",
        "description": (
            "Break staple strands at regular intervals using simple spacing. "
            "For each staple longer than max_staple_len, splits at target spacing. "
            "For Dijkstra-optimized breaks, use autoBreakStaples instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {
                    "type": "integer",
                    "description": "Only break staples on this helix (optional)."
                },
                "spacing": {
                    "type": "integer",
                    "description": "Target staple length between breaks (default: midpoint of min/max)."
                },
                "min_staple_len": {
                    "type": "integer",
                    "description": "Don't break staples shorter than this (default 30)."
                },
                "max_staple_len": {
                    "type": "integer",
                    "description": "Only break staples longer than this (default 40)."
                }
            },
            "required": []
        }
    },
    {
        "name": "listStaples",
        "description": (
            "List all staple oligos with their lengths, colors, and helix spans. "
            "Useful for checking staple lengths before/after breaking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {
                    "type": "integer",
                    "description": "Filter to staples touching this helix (optional)."
                }
            },
            "required": []
        }
    },
    {
        "name": "planScaffoldRouting",
        "description": (
            "Plan AND execute a complete scaffold routing for a 2×N grid design "
            "in one atomic operation. Creates a single closed loop visiting all "
            "helices using half-crossovers, then removes dangling strand fragments. "
            "Wrapped in one undo macro.\n\n"
            "Use this instead of addCrossoversForPair when the goal is a single "
            "contiguous scaffold routing. Works for any 2×N grid (2×2, 2×3, …, 2×N). "
            "For non-2×N layouts, use addCrossoversForPair manually.\n\n"
            "IMPORTANT: Call createHelicesWithStrands first to create the helices "
            "and strands, then call planScaffoldRouting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type to route (default: scaffold)."
                }
            },
            "required": []
        }
    },
    {
        "name": "deleteExposedFragments",
        "description": (
            "Delete strand segments that have an exposed (unconnected) 5' or 3' end. "
            "After crossover placement, short fragments remain outside the crossover "
            "region. Call this after placing all crossovers to clean up the design. "
            "planScaffoldRouting already calls this automatically — only use "
            "deleteExposedFragments separately if you placed crossovers manually."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type to clean up (default: scaffold)."
                }
            },
            "required": []
        }
    },

    {
        "name": "deleteOrphanFragments",
        "description": (
            "Delete strand segments where BOTH the 5' and 3' termini are exposed "
            "(unconnected) on the same helix — i.e. the strand has no crossover "
            "connections anywhere. "
            "These are edge fragments left over after planScaffoldRouting() places "
            "crossovers at valid interior positions (e.g. at index 5 and 68 on an "
            "84 bp helix, leaving fragments at 0-4 and 69-83). "
            "Call this after planScaffoldRouting() and before verifyScaffoldRouting(). "
            "Unlike deleteExposedFragments(), this will NOT remove strands that are "
            "part of an incomplete routing — those have at least one crossover "
            "connection, so only one end is free."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Which strand type to clean up (default: scaffold)."
                }
            },
            "required": []
        }
    },

    # ==================== LEVEL 1 — QUERY PRIMITIVES ====================

    {
        "name": "listHelices",
        "description": "List all virtual helices in the active part with their numbers, coordinates, and basic info.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "getPartSize",
        "description": "Return the current max base index (length) of the active part.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "listCrossovers",
        "description": "List crossovers in the design, optionally filtered by helix or strand type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {
                    "type": "integer",
                    "description": "If specified, only show crossovers on this helix (optional)."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Filter by strand type (optional)."
                }
            },
            "required": []
        }
    },
    {
        "name": "getSelectedStrands",
        "description": "Return information about the currently selected strands in the GUI.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "verifyDesign",
        "description": "Run design verification and return a quality score with any issues found.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "verifyScaffoldRouting",
        "description": (
            "Verify scaffold routing quality. Returns a reward score (0.0–1.0) and "
            "diagnostic info for two checks:\n"
            "  1. verifyNoScaffoldTermini — no scaffold strand has a free 5' or 3' end.\n"
            "  2. verifyScaffoldClosedLoop — scaffold forms exactly ONE closed loop.\n"
            "reward=1.0: perfect (single closed loop, no termini) → trajectory PASSED.\n"
            "reward=0.5: multiple closed loops, no open ends → missing crossovers between segments.\n"
            "reward=0.0: any exposed terminus → fragment deletion or crossover placement failed.\n"
            "Call this after planScaffoldRouting to confirm success."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "getHoneycombPositions",
        "description": (
            "Return standard honeycomb lattice [row, col] positions for N helices. "
            "Use this to get valid positions before calling createHelicesWithStrands."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "num_helices": {
                    "type": "integer",
                    "description": "Number of helix positions to return (e.g. 6 for a 6-helix bundle)."
                }
            },
            "required": ["num_helices"]
        }
    },
    {
        "name": "getValidCrossoverPositions",
        "description": "Return valid crossover positions between two neighboring helices for a given strand type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix1": {"type": "integer", "description": "First helix number."},
                "helix2": {"type": "integer", "description": "Second helix number."},
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Strand type to check."
                }
            },
            "required": ["helix1", "helix2", "strand_type"]
        }
    },

    # ==================== LEVEL 1 — MODIFYING PRIMITIVES ====================

    {
        "name": "createHelix",
        "description": "Create a single virtual helix at the given honeycomb lattice position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "row": {"type": "integer", "description": "Row coordinate on the honeycomb lattice."},
                "col": {"type": "integer", "description": "Column coordinate on the honeycomb lattice."}
            },
            "required": ["row", "col"]
        }
    },
    {
        "name": "createScaffoldStrand",
        "description": "Create a scaffold strand on the specified helix.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {"type": "integer", "description": "Helix number."},
                "start_idx": {"type": "integer", "description": "Start base pair index."},
                "length": {"type": "integer", "description": "Strand length in base pairs."}
            },
            "required": ["helix_num", "start_idx", "length"]
        }
    },
    {
        "name": "createStapleStrand",
        "description": "Create a staple strand on the specified helix.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {"type": "integer", "description": "Helix number."},
                "start_idx": {"type": "integer", "description": "Start base pair index."},
                "length": {"type": "integer", "description": "Strand length in base pairs."}
            },
            "required": ["helix_num", "start_idx", "length"]
        }
    },
    {
        "name": "createCrossover",
        "description": (
            "Create a double crossover (two half-crossovers at adjacent positions) between two helices. "
            "This is the standard crossover in DNA origami. The paired position is found automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "helix1": {"type": "integer", "description": "First helix number."},
                "idx1": {"type": "integer", "description": "Base pair index on helix1."},
                "helix2": {"type": "integer", "description": "Second helix number (must neighbor helix1)."},
                "idx2": {"type": "integer", "description": "Base pair index on helix2."},
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Strand type for the crossover."
                }
            },
            "required": ["helix1", "idx1", "helix2", "idx2", "strand_type"]
        }
    },
    {
        "name": "removeCrossover",
        "description": "Remove an existing crossover at the given position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {"type": "integer", "description": "Helix number where the crossover is."},
                "idx": {"type": "integer", "description": "Base pair index of the crossover."},
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Strand type of the crossover."
                }
            },
            "required": ["helix_num", "idx", "strand_type"]
        }
    },
    {
        "name": "extendPartSize",
        "description": "Extend the active part's size to accommodate at least min_length_needed base pairs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_length_needed": {
                    "type": "integer",
                    "description": "The minimum number of base pairs the part needs to accommodate."
                }
            },
            "required": ["min_length_needed"]
        }
    },
    {
        "name": "resizeStrand",
        "description": "Resize a specific strand by setting new low and high end indices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {"type": "integer", "description": "Helix number."},
                "idx": {"type": "integer", "description": "Current index of the strand (any position within it)."},
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Strand type."
                },
                "new_low": {"type": "integer", "description": "New low end index."},
                "new_high": {"type": "integer", "description": "New high end index."}
            },
            "required": ["helix_num", "idx", "strand_type", "new_low", "new_high"]
        }
    },
    {
        "name": "deleteStrand",
        "description": "Delete a strand at the given helix and index.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {"type": "integer", "description": "Helix number."},
                "idx": {"type": "integer", "description": "Index within the strand to delete."},
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Strand type."
                }
            },
            "required": ["helix_num", "idx", "strand_type"]
        }
    },
    {
        "name": "selectStrand",
        "description": "Select a strand in the GUI at the given helix and index.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {"type": "integer", "description": "Helix number."},
                "idx": {"type": "integer", "description": "Index within the strand."},
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Strand type."
                }
            },
            "required": ["helix_num", "idx", "strand_type"]
        }
    },
    {
        "name": "selectEndpoint",
        "description": "Select one endpoint of a strand.",
        "input_schema": {
            "type": "object",
            "properties": {
                "helix_num": {"type": "integer", "description": "Helix number."},
                "idx": {"type": "integer", "description": "Index within the strand."},
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple"],
                    "description": "Strand type."
                },
                "which_end": {
                    "type": "string",
                    "enum": ["low", "high"],
                    "description": "Which end of the strand to select."
                }
            },
            "required": ["helix_num", "idx", "strand_type", "which_end"]
        }
    },
    {
        "name": "clearSelection",
        "description": "Clear all currently selected items in the GUI.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "moveSelection",
        "description": "Move or resize the currently selected elements by delta base pairs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "delta": {
                    "type": "integer",
                    "description": "Number of base pairs to move (positive = right/higher index, negative = left/lower index)."
                }
            },
            "required": ["delta"]
        }
    },

    # ==================== DONE TOOL ====================

    {
        "name": "done",
        "description": (
            "Signal that the task is complete. Call this when you have finished "
            "all requested operations and verified the result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "A brief summary of what was accomplished."
                }
            },
            "required": ["message"]
        }
    }
]

# ==================== RLVR TOOL SUBSETS ====================

RLVR_SCAFFOLD_TOOL_NAMES = {
    'analyzeDesign', 'describeHelix', 'getNeighborPairs', 'listHelices',
    'inferScaffoldRoute',
    'verifyScaffoldRouting',
    'planScaffoldRouting',
    'deleteOrphanFragments',   # safe: AND condition (both ends free, no crossover)
    'done',
}
# deleteExposedFragments (OR condition) is intentionally excluded from RLVR tools.
# It deletes any strand with at least one free end, which destroys strands that are
# part of an incomplete but in-progress routing.
# deleteOrphanFragments (AND condition) is safe: only removes edge fragments that
# were never connected via crossover anywhere — exactly the cleanup needed after
# planScaffoldRouting() places crossovers at interior positions.
RLVR_SCAFFOLD_TOOLS = [t for t in TOOL_SCHEMAS if t['name'] in RLVR_SCAFFOLD_TOOL_NAMES]
