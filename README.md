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
- [Envoi par e-mail (optionnel)](#envoi-par-e-mail-optionnel)
- [Performances et modèles Whisper](#performances-et-modèles-whisper)
- [Créer un exécutable Windows](#créer-un-exécutable-windows)
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

Quand c'est possible, l'outil **devine en plus les vrais noms** des locuteurs à
partir du **tour de table** (« Bonjour, Alice à l'appareil… ») et remplace
`Locuteur 1/2/…` par ces noms avant la synthèse. Cette détection est
désactivable via la case **« Deviner les vrais noms… »** (ou `infer_speaker_names`
dans la configuration).

> ℹ️ La diarisation **dégrade gracieusement** : si la dépendance ou le jeton
> manquent, l'outil bascule automatiquement sur une transcription simple et le
> traitement se poursuit (la raison est indiquée dans la barre de statut).
> Si un nom n'est pas clairement énoncé, le libellé « Locuteur N » est conservé
> (aucun nom n'est inventé).

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

# Exporter aussi la synthèse en Word et PDF
pmo-notes process reunion.wav --docx --pdf

# Envoyer la synthèse par e-mail (serveur SMTP configuré dans config.json)
pmo-notes process reunion.wav --email

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
| `infer_speaker_names` | deviner les noms (tour de table) | `true` / `false` |
| `output_dir` | dossier de sortie | chemin |
| `save_transcript` / `keep_audio` | conserver `.txt` / `.wav` | `true` / `false` |
| `export_docx` / `export_pdf` | générer aussi `.docx` / `.pdf` | `true` / `false` |
| `email_enabled` | envoyer la synthèse par e-mail | `true` / `false` |
| `email_to` / `email_from` | destinataires / expéditeur | adresses e-mail |
| `smtp_host` / `smtp_port` | serveur SMTP | ex. `smtp.exemple.fr` / `587` |
| `smtp_user` / `smtp_password` | identifiants SMTP | mot de passe : préférez `PMO_SMTP_PASSWORD` |
| `smtp_use_tls` | STARTTLS | `true` / `false` |

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

Vous pouvez en plus générer la synthèse au format **Word (`.docx`)** et/ou
**PDF** : cochez « Word (.docx) » / « PDF (.pdf) » dans l'interface (ou activez
`export_docx` / `export_pdf` dans la configuration ; en ligne de commande,
ajoutez `--docx` / `--pdf`). Ces documents reprennent la même structure (titres
de sections, puces, responsables en gras). *(Aucun logiciel bureautique n'est
requis : la génération utilise `python-docx` et `reportlab`, installés avec les
dépendances.)*

---

## Envoi par e-mail (optionnel)

L'outil peut **envoyer automatiquement la synthèse par e-mail**, avec les
documents en pièces jointes, dès qu'elle est produite.

1. Configurez le serveur SMTP dans `config.json` :
   ```json
   {
     "email_enabled": true,
     "email_to": "destinataire@exemple.fr, autre@exemple.fr",
     "email_from": "moi@exemple.fr",
     "smtp_host": "smtp.exemple.fr",
     "smtp_port": 587,
     "smtp_user": "moi@exemple.fr",
     "smtp_use_tls": true
   }
   ```
2. Fournissez le **mot de passe** via une variable d'environnement (recommandé) :
   ```powershell
   setx PMO_SMTP_PASSWORD "votre_mot_de_passe"
   ```
   (ou via le champ `smtp_password` de la configuration).
3. Dans l'interface, cochez **« Envoyer la synthèse par e-mail »** et renseignez
   les destinataires. En ligne de commande, ajoutez **`--email`**.

- Port **587** → STARTTLS (par défaut) ; port **465** → SSL implicite.
- Pièces jointes : la synthèse Markdown et, s'ils sont générés, les documents
  `.docx` / `.pdf`.
- L'envoi **dégrade gracieusement** : un échec est signalé dans la barre de
  statut, mais la synthèse reste enregistrée localement.

> 🔐 Pour Gmail ou Microsoft 365 avec double authentification, créez un **mot de
> passe d'application** dédié plutôt que d'utiliser votre mot de passe principal.

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

## Créer un exécutable Windows

Pour distribuer l'outil à des utilisateurs **sans installer Python**, vous pouvez
générer un exécutable autonome avec [PyInstaller](https://pyinstaller.org/). La
recette est fournie dans le dossier [`packaging/`](packaging/).

Depuis une invite de commandes Windows, à la racine du projet :

```bat
packaging\build_windows.bat
```

Le script crée un environnement isolé, installe les dépendances + PyInstaller et
produit l'application dans **`dist\PMONotes\PMONotes.exe`** (mode « onedir » :
un dossier autonome à copier tel quel).

Détails et bonnes pratiques :

- Le **modèle Whisper n'est pas embarqué** : il se télécharge au premier
  lancement (connexion requise une fois), puis est mis en cache.
- Pour inclure la **diarisation**, dé-commentez la ligne `pyannote.audio` dans
  `build_windows.bat` avant de lancer la construction.
- L'antivirus ou SmartScreen peut signaler un exécutable PyInstaller non signé :
  c'est courant. Pour une diffusion large, envisagez une **signature de code**.
- En cas d'erreur « *ModuleNotFoundError* » au lancement de l'`.exe`, ajoutez le
  module manquant à `hiddenimports` dans `packaging/pmo-notes.spec`, puis
  reconstruisez.

> ℹ️ La construction doit être réalisée **sur une machine Windows** (l'exécutable
> est spécifique à la plateforme).

---

## Confidentialité

- La **capture** et la **transcription** se font **localement** : l'audio ne
  quitte pas votre machine.
- Avec le moteur **Ollama**, la **synthèse aussi** est locale : aucune donnée de
  réunion n'est envoyée à un service tiers.
- Avec le moteur **API Claude**, **la transcription textuelle** est envoyée à
  l'API Anthropic pour produire la synthèse. À choisir en connaissance de cause
  selon la sensibilité des réunions.
- Si l'**envoi par e-mail** est activé, la synthèse et ses pièces jointes
  transitent par le serveur SMTP que vous configurez.
- Pensez à informer les participants et à respecter les règles internes et
  légales applicables à l'enregistrement des réunions.

---

## Limitations connues

- **Identification des locuteurs (diarisation)** : prise en charge en **option**
  (voir [la section dédiée](#identifier-les-locuteurs-optionnel)). Les vrais
  **noms** sont devinés lorsqu'ils sont énoncés (tour de table) ; à défaut, le
  libellé `Locuteur N` est conservé — aucun nom n'est inventé.
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
├── speaker_names.py    Détection des vrais noms (tour de table) via le modèle
├── summarization/      Moteurs de synthèse
│   ├── base.py         Logique commune (map-reduce des longues réunions)
│   ├── ollama.py       Backend local Ollama
│   └── claude.py       Backend API Claude (Anthropic)
├── email_sender.py     Envoi de la synthèse par e-mail (SMTP, optionnel)
├── prompts.py          Invites de synthèse (structure imposée)
├── pipeline.py         Orchestration enregistrement → synthèse → export
├── export.py           Écriture des synthèses (.md, .docx, .pdf) + transcription
├── config.py           Configuration (JSON)
├── gui.py              Interface graphique (Tkinter)
└── cli.py              Interface en ligne de commande
tests/                  Tests unitaires (pytest)
packaging/              Recette PyInstaller (exécutable Windows)
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
