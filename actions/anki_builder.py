"""
anki_builder.py — incremental Anki deck builder on top of genanki.
"""
from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _stable_id(seed: str) -> int:
    h = hashlib.sha1(seed.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


class AnkiBuilder:
    """Builds genanki decks and writes .apkg files."""

    def __init__(self) -> None:
        try:
            import genanki  # type: ignore
            self._genanki = genanki
        except ImportError as e:
            raise RuntimeError("genanki is required: pip install genanki") from e
        self._decks: dict[str, dict] = {}

    def create_deck(self, name: str, description: str = "") -> str:
        """Create a deck; returns its name (used as the public key)."""
        if name in self._decks:
            raise ValueError(f"deck already exists: {name}")
        deck_id = _stable_id(name)
        deck = self._genanki.Deck(deck_id, name)
        deck.description = description
        model_id = _stable_id(f"{name}-model")
        model = self._genanki.Model(
            model_id,
            "JARVIS Card",
            fields=[{"name": "Front"}, {"name": "Back"}],
            templates=[{
                "name": "Card 1",
                "qfmt": "{{Front}}",
                "afmt": '{{Front}}<hr id="answer">{{Back}}',
            }],
            css=".card { font-family: arial; font-size: 20px; text-align: center; color: black; background: white; }",
        )
        self._decks[name] = {"deck": deck, "model": model}
        return name

    def add_card(self, front: str, back: str, deck: str) -> bool:
        entry = self._decks.get(deck)
        if not entry:
            raise ValueError(f"unknown deck: {deck}")
        try:
            entry["deck"].add_note(self._genanki.Note(
                model=entry["model"],
                fields=[front, back],
            ))
            return True
        except Exception as e:
            print(f"[AnkiBuilder] add_card error: {e}")
            return False

    def add_image_card(self, front: str, back: str, image_path: Union[str, Path],
                       deck: str) -> bool:
        img = Path(image_path)
        if img.exists():
            front = f"{front}<br><img src='{img.as_uri()}'>"
        return self.add_card(front, back, deck)

    def export_deck(self, deck: str, output_path: Union[str, Path]) -> bool:
        entry = self._decks.get(deck)
        if not entry:
            raise ValueError(f"unknown deck: {deck}")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._genanki.Package(entry["deck"]).write_to_file(str(output))
            return output.exists()
        except Exception as e:
            print(f"[AnkiBuilder] export error: {e}")
            return False

    def export_all(self, output_path: Union[str, Path]) -> bool:
        if not self._decks:
            return False
        decks = [e["deck"] for e in self._decks.values()]
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._genanki.Package(decks).write_to_file(str(output))
            return output.exists()
        except Exception as e:
            print(f"[AnkiBuilder] export_all error: {e}")
            return False

    def import_from_csv(self, csv_path: Union[str, Path],
                        output_path: Union[str, Path],
                        deck_name: Optional[str] = None,
                        front_col: int = 0,
                        back_col: int = 1) -> bool:
        deck_name = deck_name or Path(csv_path).stem
        self.create_deck(deck_name)
        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) <= max(front_col, back_col):
                    continue
                self.add_card(row[front_col], row[back_col], deck_name)
        return self.export_deck(deck_name, output_path)

    def list_decks(self) -> list[str]:
        return list(self._decks.keys())