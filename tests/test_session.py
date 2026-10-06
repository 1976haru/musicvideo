from mvstudio.session import LyricsWorldSession


def test_pasted_lyrics_session_analysis():
    s = LyricsWorldSession(lyrics_text="새벽 역에 혼자 앉아\n비가 창문을 적시고\n붉은 표를 쥐고 기다려\n다시 만나면 손을 흔들게\n다시 만나면 손을 흔들게", duration_sec=100)
    s.analyze()
    assert len(s.lines) == 5
    assert s.analysis is not None
    assert len(s.concepts) == 3
    assert s.selected_concept_id == s.concepts[0].concept_id
    assert s.to_dict()["schema_version"] == "0.8"


def test_concept_selection():
    s = LyricsWorldSession(lyrics_text="바람이 불고 오래된 사진을 보았어\n내일이면 나는 떠날 거야", duration_sec=60)
    s.analyze()
    target=s.concepts[-1].concept_id
    s.select_concept(target)
    assert s.selected_concept_id == target
