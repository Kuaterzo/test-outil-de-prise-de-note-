from pmo_notes.speaker_names import (
    apply_speaker_names,
    infer_speaker_names,
    name_speakers,
    parse_name_mapping,
)


class FakeSummarizer:
    """Moteur factice : renvoie une réponse figée pour l'appel `complete`."""

    def __init__(self, response: str):
        self.response = response
        self.last_prompt = None

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.last_prompt = user_prompt
        return self.response


def test_parse_mapping_basic():
    mapping = parse_name_mapping('{"Locuteur 1": "Alice", "Locuteur 2": "Bob"}')
    assert mapping == {"Locuteur 1": "Alice", "Locuteur 2": "Bob"}


def test_parse_mapping_tolerates_surrounding_text():
    raw = 'Voici le résultat :\n```json\n{"Locuteur 1": "Alice"}\n```\nVoilà.'
    assert parse_name_mapping(raw) == {"Locuteur 1": "Alice"}


def test_parse_mapping_filters_invalid_entries():
    raw = '{"Locuteur 1": "Alice", "autre": "x", "Locuteur 2": ""}'
    assert parse_name_mapping(raw) == {"Locuteur 1": "Alice"}


def test_parse_mapping_invalid_json_returns_empty():
    assert parse_name_mapping("pas de json ici") == {}
    assert parse_name_mapping("") == {}


def test_apply_names_replaces_labels():
    transcript = "Locuteur 1 : Bonjour\nLocuteur 2 : Salut"
    out = apply_speaker_names(transcript, {"Locuteur 1": "Alice", "Locuteur 2": "Bob"})
    assert out == "Alice : Bonjour\nBob : Salut"


def test_apply_names_longest_label_first():
    # « Locuteur 1 » ne doit pas écraser « Locuteur 10 ».
    transcript = "Locuteur 10 : a\nLocuteur 1 : b"
    out = apply_speaker_names(transcript, {"Locuteur 1": "Bob", "Locuteur 10": "Zoe"})
    assert out == "Zoe : a\nBob : b"


def test_infer_and_name_speakers():
    summ = FakeSummarizer('{"Locuteur 1": "Alice"}')
    transcript = "Locuteur 1 : Bonjour je suis Alice\nLocuteur 2 : ok"
    mapping = infer_speaker_names(summ, transcript)
    assert mapping == {"Locuteur 1": "Alice"}

    renamed, mapping2 = name_speakers(summ, transcript)
    assert renamed.startswith("Alice : Bonjour")
    assert mapping2 == {"Locuteur 1": "Alice"}
