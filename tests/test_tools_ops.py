from agentic_ai.tools.ops import Calculator


def test_calculator_basic():
    calc = Calculator()
    assert calc.run("2 + 2") == "4"
    assert "ERROR" in calc.run(
        "__import__(os).system(echo 'malicious')"
    )  # Should not allow arbitrary code execution
