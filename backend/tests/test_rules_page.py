import gostdoc_engine.rules  # noqa: F401
from gostdoc_engine.analyze import analyze
from gostdoc_engine.profile import builtin_profile
from gostdoc_engine.rules.base import REGISTRY
from tests.builders import build_docx

P = builtin_profile("gost-7.32-2017")
BLOCKS = [("p", "Текст.")]


def check(key, doc):
    return REGISTRY[key]().check(analyze(doc), P.rules[key])


def test_margins_ok():
    assert check("page.margins", build_docx(BLOCKS)) == []


def test_margins_violation_and_fix():
    doc = build_docx(BLOCKS, margins_mm=(20, 20, 20, 10))
    issues = check("page.margins", doc)
    assert [(i.expected, i.actual) for i in issues] == [("30 мм", "20 мм"), ("15 мм", "10 мм")]
    assert all(i.paragraph_index is None for i in issues)
    REGISTRY["page.margins"]().fix(analyze(doc), P.rules["page.margins"])
    assert check("page.margins", doc) == []


def test_margins_all_sections_checked():
    from docx.enum.section import WD_SECTION
    from docx.shared import Mm

    doc = build_docx(BLOCKS)
    s2 = doc.add_section(WD_SECTION.NEW_PAGE)
    s2.left_margin = Mm(10)
    s2.page_width, s2.page_height = Mm(210), Mm(297)
    assert len(check("page.margins", doc)) == 1
    REGISTRY["page.margins"]().fix(analyze(doc), P.rules["page.margins"])
    assert check("page.margins", doc) == []


def test_size_ok_and_violation():
    from docx.shared import Mm

    assert check("page.size", build_docx(BLOCKS)) == []
    doc = build_docx(BLOCKS)
    s = doc.sections[0]
    s.page_width, s.page_height = Mm(216), Mm(279)
    issues = check("page.size", doc)
    assert len(issues) == 1 and "A4" in issues[0].expected
    REGISTRY["page.size"]().fix(analyze(doc), P.rules["page.size"])
    assert check("page.size", doc) == []
