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
            "which positions are occupied, available, and recommended. "
            "Use before addCrossoversForPair to understand valid placement options."
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

    # ==================== LEVEL 2 — BATCH EXECUTION TOOLS ====================

    {
        "name": "createHelicesWithStrands",
        "description": (
            "Create multiple helices with strands in one atomic operation. "
            "Auto-extends part size as needed. Preferred over creating helices one at a time. "
            "Use getHoneycombPositions first to get valid [row, col] positions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "positions": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2
                    },
                    "description": "List of [row, col] pairs for helix positions."
                },
                "strand_type": {
                    "type": "string",
                    "enum": ["scaffold", "staple", "both"],
                    "description": "Whether to create scaffold strands, staple strands, or both."
                },
                "length": {
                    "type": "integer",
                    "description": "Strand length in base pairs. Use multiples of 21 (e.g. 84, 126)."
                }
            },
            "required": ["positions", "strand_type", "length"]
        }
    },
    {
        "name": "addCrossoversForPair",
        "description": (
            "Add crossovers between two neighboring helices. "
            "Auto-computes valid positions if not specified. "
            "Each call is wrapped in one undo macro for atomic undo."
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
            "to connect all helices."
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
