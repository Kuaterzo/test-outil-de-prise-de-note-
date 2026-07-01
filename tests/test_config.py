from pmo_notes.config import Config


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(backend="claude", ollama_model="mistral", whisper_model="medium")
    cfg.save(path)

    loaded = Config.load(path)
    assert loaded.backend == "claude"
    assert loaded.ollama_model == "mistral"
    assert loaded.whisper_model == "medium"


def test_load_missing_returns_defaults(tmp_path):
    cfg = Config.load(tmp_path / "absent.json")
    assert cfg.backend == "ollama"
    assert cfg.claude_model == "claude-opus-4-8"


def test_from_dict_ignores_unknown_keys():
    cfg = Config.from_dict({"backend": "claude", "inconnu": 123})
    assert cfg.backend == "claude"
    assert not hasattr(cfg, "inconnu")


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ pas du json", encoding="utf-8")
    cfg = Config.load(path)
    assert cfg.backend == "ollama"


def test_validate_detects_bad_backend():
    problems = Config(backend="gpt").validate()
    assert any("Backend" in p for p in problems)


def test_resolved_output_dir_expands_home():
    cfg = Config(output_dir="~/quelque_part")
    assert "~" not in str(cfg.resolved_output_dir())
