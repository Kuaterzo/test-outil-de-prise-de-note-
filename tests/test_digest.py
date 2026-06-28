import pytest

from pmo_notes.digest import (
    DIGEST_SYSTEM_PROMPT,
    DigestError,
    build_digest_user_prompt,
    collect_syntheses,
    make_digest,
)


class FakeSummarizer:
    def __init__(self, response="RAPPORT"):
        self.response = response
        self.last_system = None

    def complete(self, system_prompt, user_prompt):
        self.last_system = system_prompt
        return self.response


def _write(d, name, text):
    (d / name).write_text(text, encoding="utf-8")


def test_collect_filters_and_sorts(tmp_path):
    _write(tmp_path, "2026-06-25_10h00_Daily.md", "C")
    _write(tmp_path, "2026-06-20_09h00_COPIL.md", "A")
    _write(tmp_path, "2026-06-22_14h30_Atelier.md", "B")
    _write(tmp_path, "digest_2026-06-25.md", "ignore")      # pas un fichier de réunion
    _write(tmp_path, "2026-06-21_11h00_Vide.md", "   ")      # vide -> ignoré
    _write(tmp_path, "notes.md", "x")                        # pas de préfixe date

    docs = collect_syntheses(tmp_path)
    assert [d.date for d in docs] == ["2026-06-20", "2026-06-22", "2026-06-25"]
    assert [d.text for d in docs] == ["A", "B", "C"]


def test_collect_date_filters(tmp_path):
    _write(tmp_path, "2026-06-20_09h00_A.md", "A")
    _write(tmp_path, "2026-06-22_09h00_B.md", "B")
    _write(tmp_path, "2026-06-25_09h00_C.md", "C")

    assert [d.date for d in collect_syntheses(tmp_path, since="2026-06-22")] == [
        "2026-06-22", "2026-06-25",
    ]
    assert [d.date for d in collect_syntheses(tmp_path, until="2026-06-22")] == [
        "2026-06-20", "2026-06-22",
    ]


def test_collect_missing_dir(tmp_path):
    assert collect_syntheses(tmp_path / "absent") == []


def test_build_prompt_contains_texts_and_count(tmp_path):
    _write(tmp_path, "2026-06-20_09h00_A.md", "contenu A")
    _write(tmp_path, "2026-06-22_09h00_B.md", "contenu B")
    docs = collect_syntheses(tmp_path)
    prompt = build_digest_user_prompt(docs, "Projet Phénix")
    assert "Projet Phénix" in prompt
    assert "Nombre de réunions : 2" in prompt
    assert "contenu A" in prompt and "contenu B" in prompt


def test_make_digest_uses_system_prompt(tmp_path):
    _write(tmp_path, "2026-06-20_09h00_A.md", "A")
    docs = collect_syntheses(tmp_path)
    summ = FakeSummarizer("RAPPORT")
    assert make_digest(summ, docs, "Projet") == "RAPPORT"
    assert summ.last_system == DIGEST_SYSTEM_PROMPT


def test_make_digest_empty_raises():
    with pytest.raises(DigestError):
        make_digest(FakeSummarizer(), [], "Projet")
