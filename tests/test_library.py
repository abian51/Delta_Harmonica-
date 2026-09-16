import pytest

import dhs.library as library


def test_library_supports_more_than_six_songs(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "data_dir", lambda: tmp_path)
    for number in range(8):
        library.save_song(f"song-{number}", {"name": f"song-{number}", "midi_path": f"{number}.mid"})
    assert len(library.list_songs()) == 8


def test_delete_refuses_path_outside_library(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "data_dir", lambda: tmp_path)
    with pytest.raises(ValueError, match="outside"):
        library.delete_song(tmp_path / "other.json")

