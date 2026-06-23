"""Assistant local de prise de notes et de synthèse de réunions pour PMO.

Le paquet est volontairement découpé pour que les modules « légers »
(`config`, `prompts`, `export`, `summarization.base`) puissent être importés
et testés sans installer les dépendances lourdes (audio, Whisper, SDK Claude),
qui ne sont importées qu'au moment de leur utilisation effective.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
