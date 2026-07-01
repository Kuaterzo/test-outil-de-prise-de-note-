from pmo_notes.diarization import (
    SpeakerTurn,
    assign_speakers,
    format_labeled_transcript,
    friendly_speaker_names,
)
from pmo_notes.transcription import TranscriptSegment


def test_assign_speakers_picks_max_overlap():
    segments = [
        TranscriptSegment(0.0, 2.5, "a"),
        TranscriptSegment(3.5, 5.0, "b"),
    ]
    turns = [
        SpeakerTurn(0.0, 3.0, "SPEAKER_00"),
        SpeakerTurn(3.0, 6.0, "SPEAKER_01"),
    ]
    labeled = assign_speakers(segments, turns)
    assert [s.speaker for s in labeled] == ["SPEAKER_00", "SPEAKER_01"]


def test_assign_speakers_inherits_previous_when_no_overlap():
    segments = [
        TranscriptSegment(0.0, 1.0, "a"),
        TranscriptSegment(10.0, 11.0, "b"),  # aucun tour ne couvre cet intervalle
    ]
    turns = [SpeakerTurn(0.0, 2.0, "SPEAKER_00")]
    labeled = assign_speakers(segments, turns)
    assert [s.speaker for s in labeled] == ["SPEAKER_00", "SPEAKER_00"]


def test_assign_speakers_unknown_when_no_turns():
    labeled = assign_speakers([TranscriptSegment(0.0, 1.0, "a")], [])
    assert labeled[0].speaker == "?"


def test_friendly_names_in_order_of_appearance():
    labeled = assign_speakers(
        [TranscriptSegment(0, 1, "x"), TranscriptSegment(1, 2, "y")],
        [SpeakerTurn(0, 1, "SPEAKER_02"), SpeakerTurn(1, 2, "SPEAKER_00")],
    )
    names = friendly_speaker_names(labeled)
    assert names["SPEAKER_02"] == "Locuteur 1"
    assert names["SPEAKER_00"] == "Locuteur 2"


def test_format_merges_consecutive_same_speaker():
    labeled = assign_speakers(
        [
            TranscriptSegment(0, 1, "Bonjour"),
            TranscriptSegment(1, 2, "ça va ?"),
            TranscriptSegment(2, 3, "Oui merci"),
        ],
        [SpeakerTurn(0, 2, "S0"), SpeakerTurn(2, 3, "S1")],
    )
    text = format_labeled_transcript(labeled)
    assert text == "Locuteur 1 : Bonjour ça va ?\nLocuteur 2 : Oui merci"


def test_format_empty():
    assert format_labeled_transcript([]) == ""
