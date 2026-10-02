"""Test proving import-linter catches dependency violations."""



def test_import_linter_contract_exists() -> None:
    """Verify import-linter is installed and contract configuration exists."""
    from pathlib import Path

    linter_cfg = Path(".importlinter")
    assert linter_cfg.exists(), ".importlinter config must exist"

    content = linter_cfg.read_text()
    assert "omni_contracts imports nothing internal" in content
    assert "sandbox_runner must not import omni_db" in content
    assert "omni_agents must not import sandbox_runner" in content
