"""Tests for nk_parser v2 — stack simulation and connection extraction."""

import textwrap

import pytest

from nukebread.server.rag.nk_parser import (
    _parse_with_connections,
    _split_into_components,
    build_connections_summary,
    parse_nk_file,
)


# ---------------------------------------------------------------------------
# Minimal .nk snippets for unit testing
# ---------------------------------------------------------------------------

SIMPLE_LINEAR = textwrap.dedent("""\
    Root {
     inputs 0
    }
    Read {
     inputs 0
     name Read_BG
     xpos 0
     ypos 0
    }
    Grade {
     whitepoint {1.1 1.0 0.95 1.0}
     name Grade_Warm
     xpos 0
     ypos 50
    }
""")

BRANCHING = textwrap.dedent("""\
    Root {
     inputs 0
    }
    ColorWheel {
     inputs 0
     name ColorWheel1
    }
    set N1 [stack 0]
    Expression {
     expr2 b>0.5?0.5:b
     name ExprBlue
    }
    push $N1
    Expression {
     expr1 g>0.5?0.5:g
     name ExprGreen
    }
""")

MULTI_INPUT = textwrap.dedent("""\
    Root {
     inputs 0
    }
    Read {
     inputs 0
     name Read_BG
    }
    set Nplate [stack 0]
    Read {
     inputs 0
     name Read_CG
    }
    Grade {
     name Grade_CG
    }
    push $Nplate
    Merge2 {
     inputs 2
     operation over
     name Merge_Over
    }
""")

PUSH_ZERO = textwrap.dedent("""\
    Root {
     inputs 0
    }
    BlendMat {
     inputs 0
     name Mat1
    }
    Card2 {
     inputs 0
     name Card1
    }
    push 0
    ParticleEmitter {
     inputs 3
     name Emitter1
    }
""")

ANIMATED_KNOBS = textwrap.dedent("""\
    Root {
     inputs 0
    }
    Transform {
     inputs 0
     translate {{curve i x1 -670 x10 380} {curve i x1 310 x10 -430}}
     scale 0.26
     name Transform1
    }
""")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseConnections:
    """Test the stack simulation and connection extraction."""

    def test_simple_linear(self):
        nodes = _parse_with_connections(SIMPLE_LINEAR)
        assert len(nodes) == 2

        read_bg = nodes[0]
        grade = nodes[1]

        assert read_bg["name"] == "Read_BG"
        assert read_bg["inputs"] == []

        assert grade["name"] == "Grade_Warm"
        assert len(grade["inputs"]) == 1
        assert grade["inputs"][0]["source_node"] == "Read_BG"
        assert grade["inputs"][0]["input_index"] == 0

    def test_branching_set_push(self):
        nodes = _parse_with_connections(BRANCHING)
        assert len(nodes) == 3

        cw = nodes[0]
        blue = nodes[1]
        green = nodes[2]

        assert cw["inputs"] == []  # source node

        # Both expressions should connect to ColorWheel1
        assert len(blue["inputs"]) == 1
        assert blue["inputs"][0]["source_node"] == "ColorWheel1"

        assert len(green["inputs"]) == 1
        assert green["inputs"][0]["source_node"] == "ColorWheel1"

    def test_multi_input_merge(self):
        nodes = _parse_with_connections(MULTI_INPUT)
        assert len(nodes) == 4

        merge = next(n for n in nodes if n["name"] == "Merge_Over")
        assert len(merge["inputs"]) == 2

        # Input 0 = Read_BG (pushed via $Nplate), Input 1 = Grade_CG
        sources = {c["input_index"]: c["source_node"] for c in merge["inputs"]}
        assert sources[0] == "Read_BG"
        assert sources[1] == "Grade_CG"

    def test_push_zero_disconnected(self):
        nodes = _parse_with_connections(PUSH_ZERO)
        assert len(nodes) == 3

        emitter = next(n for n in nodes if n["name"] == "Emitter1")
        # push 0 means input 0 is disconnected (None → not in list)
        # Card1 is input 1, Mat1 is input 2
        sources = {c["input_index"]: c["source_node"] for c in emitter["inputs"]}
        assert 0 not in sources  # disconnected
        assert sources[1] == "Card1"
        assert sources[2] == "Mat1"

    def test_animated_detection(self):
        nodes = _parse_with_connections(ANIMATED_KNOBS)
        assert len(nodes) == 1

        xform = nodes[0]
        translate_knob = next(k for k in xform["knobs"] if k["name"] == "translate")
        assert translate_knob["animated"] is True
        assert translate_knob["expression"] is not None  # stored as expression

        scale_knob = next(k for k in xform["knobs"] if k["name"] == "scale")
        assert scale_knob["animated"] is False
        assert scale_knob["value"] == 0.26

    def test_skip_classes(self):
        """Viewer, BackdropNode, StickyNote should be skipped."""
        text = textwrap.dedent("""\
            Root {
             inputs 0
            }
            Read {
             inputs 0
             name Read1
            }
            Viewer {
             name Viewer1
            }
            StickyNote {
             inputs 0
             name StickyNote1
            }
        """)
        nodes = _parse_with_connections(text)
        names = [n["name"] for n in nodes]
        assert "Read1" in names
        assert "Viewer1" not in names
        assert "StickyNote1" not in names


class TestSplitComponents:
    """Test connected component splitting."""

    def test_single_component(self):
        nodes = _parse_with_connections(SIMPLE_LINEAR)
        components = _split_into_components(nodes)
        assert len(components) == 1

    def test_independent_branches(self):
        """Two disconnected Read nodes should form two components."""
        text = textwrap.dedent("""\
            Root {
             inputs 0
            }
            Read {
             inputs 0
             name Read_A
            }
            Grade {
             name Grade_A
            }
            Read {
             inputs 0
             name Read_B
            }
            Blur {
             name Blur_B
            }
        """)
        nodes = _parse_with_connections(text)
        components = _split_into_components(nodes)
        assert len(components) == 2

        comp_names = [sorted(n["name"] for n in c) for c in components]
        assert ["Grade_A", "Read_A"] in comp_names
        assert ["Blur_B", "Read_B"] in comp_names


class TestConnectionsSummary:

    def test_linear_summary(self):
        nodes = _parse_with_connections(SIMPLE_LINEAR)
        summary = build_connections_summary(nodes)
        assert "Read" in summary
        assert "Grade" in summary
        assert "→" in summary

    def test_merge_summary(self):
        nodes = _parse_with_connections(MULTI_INPUT)
        summary = build_connections_summary(nodes)
        assert "Merge2(over)" in summary


class TestRealFiles:
    """Test against actual Nuke example scripts if available."""

    EXAMPLE_DIR = "/Applications/Nuke17.0v1/Documentation/html/content/example_scripts"

    @pytest.fixture
    def despill_path(self):
        import os
        path = f"{self.EXAMPLE_DIR}/expression_green_and_blue_despill.nk"
        if not os.path.exists(path):
            pytest.skip("Nuke example scripts not available")
        return path

    @pytest.fixture
    def motionblur_path(self):
        import os
        path = f"{self.EXAMPLE_DIR}/motionblur2d.nk"
        if not os.path.exists(path):
            pytest.skip("Nuke example scripts not available")
        return path

    def test_despill_connections(self, despill_path):
        patterns = parse_nk_file(despill_path)
        assert len(patterns) >= 1

        nodes = patterns[0]["graph"]["nodes"]
        cw = next(n for n in nodes if n["class_name"] == "ColorWheel")
        exprs = [n for n in nodes if n["class_name"] == "Expression"]

        assert len(exprs) == 2
        for expr in exprs:
            sources = [c["source_node"] for c in expr["inputs"]]
            assert cw["name"] in sources

    def test_motionblur_connections(self, motionblur_path):
        patterns = parse_nk_file(motionblur_path)
        nodes = patterns[0]["graph"]["nodes"]

        mb = next(n for n in nodes if n["class_name"] == "MotionBlur2D")
        assert len(mb["inputs"]) == 2

        sources = {c["input_index"]: c["source_node"] for c in mb["inputs"]}
        assert "AdjBBox1" in sources.values()
        assert "Tracker1" in sources.values()
