# 🎙️ Assistant de synthèse de réunions — PMO

Assistant **local** qui se connecte à la **sortie audio de votre choix**, prend
en note les réunions auxquelles vous participez (visioconférences Teams, Zoom,
Meet, …), puis en produit une **synthèse écrite structurée** :

1. une **introduction**,
2. un **résumé des échanges**,
3. les **actions à venir**, avec les **personnes concernées**,
4. une **conclusion**.

La **transcription audio → texte est entièrement locale** (Whisper). Pour la
synthèse, deux moteurs sont disponibles au choix :

| Moteur | Confidentialité | Qualité | Coût | Hors-ligne |
|---|---|---|---|---|
| **Ollama** (local, par défaut) | 🔒 rien ne quitte la machine | bonne (selon le modèle) | gratuit | ✅ |
| **API Claude** (Anthropic) | la transcription est envoyée à l'API | excellente | facturé à l'usage | ❌ |

---

## Sommaire

- [Comment ça marche](#comment-ça-marche)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Choisir le moteur de synthèse](#choisir-le-moteur-de-synthèse)
- [Capturer la bonne sortie audio](#capturer-la-bonne-sortie-audio)
- [Identifier les locuteurs (optionnel)](#identifier-les-locuteurs-optionnel)
- [Utilisation — interface graphique](#utilisation--interface-graphique)
- [Utilisation — ligne de commande](#utilisation--ligne-de-commande)
- [Configuration](#configuration)
- [Où sont enregistrées les synthèses](#où-sont-enregistrées-les-synthèses)
- [Performances et modèles Whisper](#performances-et-modèles-whisper)
- [Confidentialité](#confidentialité)
- [Limitations connues](#limitations-connues)
- [Dépannage](#dépannage)
- [Structure du projet](#structure-du-projet)

---

## Comment ça marche

```
  Réunion (Teams / Zoom / Meet …)
            │  son qui sort de vos haut-parleurs
            ▼
  ┌──────────────────────┐
  │ Capture « loopback »  │  ← soundcard (WASAPI sous Windows)
  │ de la sortie audio    │
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ Transcription locale  │  ← faster-whisper (Whisper, en français)
  └──────────┬───────────┘
             ▼
  ┌──────────────────────┐
  │ Synthèse structurée   │  ← Ollama (local)  OU  API Claude
  └──────────┬───────────┘
             ▼
  Fichier Markdown (.md) + transcription (.txt) + audio (.wav)
```

---

## Prérequis

- **Windows 10/11** (la capture de la sortie audio utilise WASAPI ; voir
  [Limitations](#limitations-connues) pour macOS/Linux).
- **Python 3.9 ou supérieur** — <https://www.python.org/downloads/>
  (à l'installation, cochez **« Add Python to PATH »**).
- Une **connexion internet** lors de la première utilisation (téléchargement du
  modèle Whisper) ; ensuite l'outil fonctionne hors-ligne avec Ollama.
- *(Aucune installation séparée de FFmpeg n'est nécessaire : `faster-whisper`
  embarque le décodage audio.)*

---

## Installation

```bash
# 1. Récupérer le projet
git clone <url-du-dépôt>
cd test-outil-de-prise-de-note-

# 2. (Recommandé) créer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Installer les dépendances
pip install -r requirements.txt
```

> 💡 Vous pouvez aussi installer l'outil comme commande : `pip install .`
> fournit alors l'exécutable `pmo-notes`.

---

## Choisir le moteur de synthèse

### Option A — 100 % local avec Ollama *(par défaut)*

1. Installez Ollama : <https://ollama.com/download>
2. Téléchargez un modèle (une fois) :
   ```bash
   ollama pull llama3.1
   ```
   D'autres modèles conviennent bien au français : `mistral`, `qwen2.5`, …
3. Ollama tourne en arrière-plan sur `http://localhost:11434`. Rien d'autre à
   faire : c'est le moteur sélectionné par défaut.

### Option B — API Claude (Anthropic)

1. Procurez-vous une clé API sur <https://console.anthropic.com/>.
2. Définissez la variable d'environnement `ANTHROPIC_API_KEY` :
   ```powershell
   # Windows (PowerShell), pour la session courante
   $env:ANTHROPIC_API_KEY = "sk-ant-..."
   # …ou de façon permanente :
   setx ANTHROPIC_API_KEY "sk-ant-..."
   ```
3. Dans l'outil, sélectionnez le moteur **« API Claude »**.

Le modèle par défaut est `claude-opus-4-8`. Le niveau d'**effort** (`low` →
`max`) règle le compromis qualité/coût ; `medium` est un bon point de départ.

---

## Capturer la bonne sortie audio

L'outil enregistre ce qui **sort** de votre périphérique audio (le son que vous
entendez), via un périphérique « **loopback** ». Concrètement :

- Mettez le son de la réunion sur le périphérique que vous comptez capturer
  (votre casque ou vos haut-parleurs).
- Dans l'outil, choisissez ce même périphérique dans la liste **« Sortie audio
  à capturer »** (bouton **Rafraîchir** pour réactualiser la liste).
- Pour **capter aussi votre propre voix** (votre micro), cochez **« Mixer aussi
  mon microphone »**. *(Fonction expérimentale : voir
  [Limitations](#limitations-connues).)*

> ℹ️ Les périphériques proposés sont les sorties « loopback » détectées par
> Windows. Si la liste est vide, vérifiez qu'un périphérique de lecture est
> actif, puis cliquez sur **Rafraîchir**.

---

## Identifier les locuteurs (optionnel)

Par défaut, l'outil produit une transcription continue. Vous pouvez activer la
**diarisation** (« qui a dit quoi ») : la transcription est alors étiquetée
`Locuteur 1 :`, `Locuteur 2 :`, … et la synthèse attribue plus fidèlement les
**propos et les actions aux bonnes personnes**.

Cette fonction est **optionnelle** et s'appuie sur
[`pyannote.audio`](https://github.com/pyannote/pyannote-audio), qui nécessite un
jeton Hugging Face gratuit :

1. Installez la dépendance :
   ```bash
   pip install "pyannote.audio>=3.1"
   # ou, depuis le projet :  pip install ".[diarization]"
   ```
2. Créez un compte sur <https://huggingface.co/> et un **jeton d'accès**
   (Settings → Access Tokens).
3. Acceptez les conditions du modèle
   `pyannote/speaker-diarization-3.1` sur sa page Hugging Face.
4. Fournissez le jeton, au choix :
   ```powershell
   setx HUGGINGFACE_TOKEN "hf_..."
   ```
   …ou via le champ `hf_token` de la configuration.
5. Cochez **« Identifier les locuteurs »** dans l'interface (ou mettez
   `"diarization": true` dans la configuration).

> ℹ️ La diarisation **dégrade gracieusement** : si la dépendance ou le jeton
> manquent, l'outil bascule automatiquement sur une transcription simple et le
> traitement se poursuit (la raison est indiquée dans la barre de statut).
> Elle ne devine pas les *noms* des personnes : les libellés restent
> « Locuteur 1/2/… », que la synthèse relie aux noms cités pendant la réunion.

---

## Utilisation — interface graphique

Lancez l'interface :

```bash
python run_gui.py
# ou, si le paquet est installé :  pmo-notes gui
```

Étapes :

1. Renseignez le **titre** de la réunion et, si vous le souhaitez, les
   **participants** (séparés par des virgules).
2. Choisissez la **sortie audio à capturer**.
3. Choisissez le **moteur de synthèse** (Local Ollama / API Claude).
4. Cliquez sur **● Démarrer** au début de la réunion.
5. Cliquez sur **■ Arrêter** à la fin : l'outil transcrit puis synthétise (la
   barre de statut indique l'avancement).
6. La synthèse s'affiche et est **enregistrée automatiquement**. Le bouton
   **« Ouvrir le dossier des synthèses »** ouvre l'emplacement des fichiers.

Vous pouvez aussi **« Charger un fichier audio… »** pour synthétiser un
enregistrement existant (`.wav`, `.mp3`, `.m4a`, …).

---

## Utilisation — ligne de commande

```bash
# Lister les périphériques détectés (sorties capturables + micros)
pmo-notes devices

# Enregistrer la sortie audio puis synthétiser
#   (Entrée pour arrêter, ou --seconds pour une durée fixe)
pmo-notes record --title "Comité de pilotage" --participants "Alice, Bob"

# Synthétiser un fichier audio existant
pmo-notes process reunion.m4a --title "Atelier cadrage"

# Forcer un moteur ponctuellement
pmo-notes process reunion.wav --backend claude
```

*(Sans installation par `pip`, remplacez `pmo-notes …` par
`python -m pmo_notes …` depuis le dossier, après avoir ajouté `src` au
`PYTHONPATH`, ou utilisez `run_gui.py` pour l'interface.)*

---

## Configuration

Les réglages sont mémorisés automatiquement dans un fichier JSON :

- **Windows** : `%APPDATA%\PMONotes\config.json`
- **Linux/macOS** : `~/.config/pmo-notes/config.json`

Un exemple commenté est fourni : [`config.example.json`](config.example.json).
Principaux champs :

| Champ | Rôle | Valeurs |
|---|---|---|
| `backend` | moteur de synthèse | `ollama`, `claude` |
| `whisper_model` | modèle de transcription | `tiny`, `base`, `small`, `medium`, `large-v3` |
| `whisper_device` | matériel de transcription | `auto`, `cpu`, `cuda` |
| `language` | langue de la réunion | `fr`, `en`, … |
| `ollama_host` / `ollama_model` | serveur et modèle Ollama | ex. `llama3.1` |
| `claude_model` / `claude_effort` | modèle et effort Claude | ex. `claude-opus-4-8` / `medium` |
| `diarization` | identifier les locuteurs | `true` / `false` |
| `diarization_model` / `hf_token` | modèle pyannote / jeton Hugging Face | ex. `pyannote/speaker-diarization-3.1` |
| `output_dir` | dossier de sortie | chemin |
| `save_transcript` / `keep_audio` | conserver `.txt` / `.wav` | `true` / `false` |

---

## Où sont enregistrées les synthèses

Par défaut dans **`~/Documents/Synthèses réunions/`**. Pour chaque réunion,
trois fichiers partageant le même préfixe horodaté sont créés :

```
2026-06-23_14h05_Comité_de_pilotage.md                ← la synthèse
2026-06-23_14h05_Comité_de_pilotage_transcription.txt ← la transcription brute
2026-06-23_14h05_Comité_de_pilotage.wav               ← l'enregistrement audio
```

La synthèse est un fichier **Markdown** respectant la structure :
`## Introduction`, `## Résumé des échanges`, `## Actions à venir`,
`## Conclusion`.

---

## Performances et modèles Whisper

| Modèle | Qualité (fr) | Vitesse | Mémoire | Conseil |
|---|---|---|---|---|
| `tiny` / `base` | correcte | très rapide | faible | tests rapides |
| `small` | bonne | rapide | modérée | **par défaut, bon compromis** |
| `medium` | très bonne | plus lent | élevée | réunions importantes |
| `large-v3` | excellente | lent | très élevée | machine puissante / GPU |

- Sur **GPU NVIDIA**, réglez `whisper_device` sur `cuda` pour une transcription
  bien plus rapide.
- Le modèle est **téléchargé une seule fois** puis mis en cache localement.

---

## Confidentialité

- La **capture** et la **transcription** se font **localement** : l'audio ne
  quitte pas votre machine.
- Avec le moteur **Ollama**, la **synthèse aussi** est locale : aucune donnée de
  réunion n'est envoyée à un service tiers.
- Avec le moteur **API Claude**, **la transcription textuelle** est envoyée à
  l'API Anthropic pour produire la synthèse. À choisir en connaissance de cause
  selon la sensibilité des réunions.
- Pensez à informer les participants et à respecter les règles internes et
  légales applicables à l'enregistrement des réunions.

---

## Limitations connues

- **Identification des locuteurs (diarisation)** : prise en charge en **option**
  (voir [la section dédiée](#identifier-les-locuteurs-optionnel)). Elle
  distingue les locuteurs (`Locuteur 1/2/…`) mais ne devine pas leurs **noms** :
  ceux-ci restent ceux **cités** pendant la réunion.
- **Mixage micro + sortie** : expérimental. Les deux flux sont alignés sur leur
  longueur commune, ce qui peut introduire un léger décalage.
- **macOS** : la capture de la sortie système nécessite un périphérique virtuel
  comme [BlackHole](https://github.com/ExistentialAudio/BlackHole) (à
  sélectionner ensuite comme périphérique de capture).
- **Linux** : fonctionne via les sources « monitor » de PulseAudio/PipeWire.

---

## Dépannage

| Symptôme | Piste |
|---|---|
| « Capture audio indisponible » | `pip install soundcard` ; vérifiez qu'un périphérique de lecture est actif, puis **Rafraîchir**. |
| Liste de périphériques vide | Branchez/activez un casque ou des haut-parleurs, cliquez sur **Rafraîchir**. |
| « Impossible de joindre Ollama » | Lancez Ollama (`ollama serve`) et installez le modèle (`ollama pull llama3.1`). |
| « Clé API Anthropic invalide ou absente » | Définissez `ANTHROPIC_API_KEY` (voir [Option B](#option-b--api-claude-anthropic)). |
| Transcription très lente | Choisissez un modèle Whisper plus léger (`small`/`base`) ou activez `cuda`. |
| Synthèse vide | La réunion était peut-être silencieuse sur le périphérique capturé ; vérifiez la sélection de la sortie. |

---

## Structure du projet

```
src/pmo_notes/
├── audio.py            Capture loopback + enregistrement WAV (soundcard)
├── transcription.py    Transcription locale (faster-whisper), segments horodatés
├── diarization.py      Identification des locuteurs (optionnel, pyannote.audio)
├── summarization/      Moteurs de synthèse
│   ├── base.py         Logique commune (map-reduce des longues réunions)
│   ├── ollama.py       Backend local Ollama
│   └── claude.py       Backend API Claude (Anthropic)
├── prompts.py          Invites de synthèse (structure imposée)
├── pipeline.py         Orchestration enregistrement → synthèse → export
├── export.py           Écriture des fichiers .md / .txt
├── config.py           Configuration (JSON)
├── gui.py              Interface graphique (Tkinter)
└── cli.py              Interface en ligne de commande
tests/                  Tests unitaires (pytest)
run_gui.py              Lanceur de l'interface sans installation
```

Lancer les tests :

```bash
pip install pytest
pytest
```

---

## Licence

MIT.
