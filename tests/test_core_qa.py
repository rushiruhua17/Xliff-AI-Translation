import pytest
from core.qa import QAChecker

def test_qa_checker_ok():
    checker = QAChecker()
    source = "Hello {0} world {1}"
    target = "Hola {0} mundo {1}"
    result = checker.check_unit(source, target, "translated")
    assert result.status == "ok"
    assert not result.issues

def test_qa_checker_missing_token():
    checker = QAChecker()
    source = "Hello {0} world {1}"
    target = "Hola {0} mundo"
    result = checker.check_unit(source, target, "translated")
    assert result.status == "error"
    assert result.issues[0].type == "missing"
    assert "{1}" in result.qa_details["missing"]

def test_qa_checker_extra_token():
    checker = QAChecker()
    source = "Hello {0}"
    target = "Hola {0} {1}"
    result = checker.check_unit(source, target, "translated")
    assert result.status == "error"
    assert result.issues[0].type == "extra"
    assert "{1}" in result.qa_details["extra"]

def test_qa_checker_invalid_token():
    checker = QAChecker()
    source = "Hello {0}"
    target = "Hola {0} {99" # Missing closing brace
    result = checker.check_unit(source, target, "translated")
    assert result.status == "error"
    assert any(i.type == "invalid" for i in result.issues)

def test_qa_checker_empty_translation():
    checker = QAChecker()
    source = "Hello"
    target = ""
    result = checker.check_unit(source, target, "translated")
    assert result.status == "warning"
    assert result.issues[0].type == "empty"
