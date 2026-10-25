# RÔLE DE CE FICHIER :
# Détermine, AVANT toute génération, si l'utilisateur demande réellement un fichier,
# sous quel(s) format(s), et selon quel mode (génération locale, téléchargement Web,
# transcription fidèle d'une image). Fournit aussi un nom de fichier adapté au contenu
# et l'évaluation "demande -> artefact attendu -> artefact réellement produit"
# utilisée par le Verifier et par le runtime UI.
#
# Règles :
#   - explication / analyse / recherche            -> aucun fichier
#   - PDF demandé                                    -> uniquement un PDF (le .tex n'est qu'un intermédiaire)
#   - Word demandé                                   -> uniquement un DOCX
#   - téléchargement demandé                         -> le fichier doit provenir du Web (jamais généré)
#   - plusieurs formats demandés                     -> uniquement ces formats

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath
from typing import Any, Iterable

# Extensions considérées comme des "livrables documentaires" soumis au contrôle
# de conformité (les fichiers de code/notes restent gérés par les contrôles
# d'écriture classiques du Verifier).
DELIVERABLE_EXTENSIONS = {
    "pdf", "docx", "doc", "odt", "rtf", "tex", "html", "htm", "xlsx", "pptx",
}

# Intermédiaires tolérés lorsqu'un format final est demandé.
INTERMEDIATE_FOR = {
    "pdf": {"tex"},
    "docx": {"md"},
}

FORMAT_SYNONYMS: list[tuple[str, str]] = [
    (r"\bdocx\b|\bword\b|\bms[\s-]?word\b|\bdocument\s+word\b|\bfichier\s+word\b|\.docx\b", "docx"),
    (r"\bpdf\b|\.pdf\b", "pdf"),
    (r"\blatex\b|\.tex\b|\bfichier\s+tex\b|\bsource\s+tex\b", "tex"),
    (r"\bhtml?\b|\bpage\s+web\b|\bsite\s+web\b|\.html?\b", "html"),
    (r"\bmarkdown\b|\.md\b", "md"),
    (r"\bexcel\b|\bxlsx\b|\btableur\b|\.xlsx\b", "xlsx"),
    (r"\bpowerpoint\b|\bpptx\b|\bdiaporama\b|\.pptx\b", "pptx"),
    (r"\bodt\b|\blibreoffice\s+writer\b", "odt"),
    (r"\bcsv\b|\.csv\b", "csv"),
    (r"\bsvg\b|\.svg\b", "svg"),
    (r"\bjson\b|\.json\b", "json"),
    (r"\bscript\s+python\b|\bprogramme\s+python\b|\bfichier\s+python\b|\.py\b", "py"),
    (r"\bmermaid\b|\.mmd\b", "mmd"),
    (r"\bdiagramme\b|\borganigramme\b|\bflowchart\b", "mmd"),
]

_CREATE_VERBS = (
    r"cree|creer|cree-moi|genere|generer|genere-moi|fais|faire|fais-moi|produis|produire|"
    r"redige|rediger|exporte|exporter|ecris|ecrire|prepare|preparer|construis|construire|"
    r"compile|compiler|convertis|convertir|transforme|transformer|mets|mettre|sauvegarde|"
    r"sauvegarder|enregistre|enregistrer|livre|livrer|donne-moi|fournis|fournir|"
    r"elabore|elaborer|concois|concevoir|developpe|create|generate|make|write|export|save|build"
)
_DOWNLOAD_VERBS = (
    r"telecharge|telecharger|telecharge-le|telecharge-la|telechargement|recupere|recuperer|"
    r"recupere-le|download|rapatrie"
)
_FORMAT_PREPOSITION = re.compile(
    r"\b(?:en|au\s+format|format|sous\s+forme\s+(?:de|d'un|d'une)|version|fichier|document|un|une)\s+"
    r"(?:pdf|word|docx|latex|tex|html|markdown|excel|xlsx|powerpoint|pptx|odt|csv|svg|json)\b"
)
_EDUCATION_SKILLS = {"bacblanc", "exercice", "dm"}

_REPRODUCE_IMAGE = re.compile(
    r"\b(?:reproduis|reproduire|recopie|recopier|retranscris|retranscrire|transcris|transcrire|"
    r"reecris|reecrire|reprends|recree|copie|tape|saisis)\b[\s\S]{0,80}?\b(?:image|photo|capture|"
    r"scan|cliche|screenshot|figure\s+jointe|piece\s+jointe)\b"
    r"|\b(?:image|photo|capture|scan)\b[\s\S]{0,40}?\b(?:reproduis|recopie|retranscris|transcris)\b"
)

_STOPWORDS = {
    # articles / prépositions / pronoms
    "le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "au", "aux", "a", "en", "et",
    "ou", "sur", "pour", "par", "avec", "dans", "sans", "sous", "moi", "me", "mon", "ma", "mes",
    "ton", "ta", "tes", "son", "sa", "ses", "ce", "cet", "cette", "ces", "qui", "que", "quoi",
    "dont", "il", "elle", "nous", "vous", "ils", "elles", "je", "tu", "on", "y", "s", "t", "j",
    "n", "ne", "pas", "plus", "tres", "bien", "tout", "toute", "tous", "toutes", "of", "the",
    "to", "and", "an", "in", "for", "on", "with", "puis", "ensuite", "aussi", "propre", "joli",
    "simple", "complet", "complete", "detaille", "detaillee", "petit", "petite", "nouveau",
    "nouvelle", "mettant", "contenant", "comprenant", "concernant", "relatif", "relative",
    "officiel", "officielle", "officiels", "officielles", "specialite", "spe", "s'il", "te", "plait", "stp", "svp",
    "workspace", "dossier", "repertoire", "lien", "liens", "internet", "web", "site", "ligne",
    # verbes de demande
    "cree", "creer", "genere", "generer", "fais", "faire", "produis", "produire", "redige",
    "rediger", "exporte", "exporter", "ecris", "ecrire", "prepare", "preparer", "construis",
    "compile", "compiler", "convertis", "transforme", "mets", "mettre", "sauvegarde", "enregistre",
    "livre", "donne", "fournis", "elabore", "concois", "developpe", "telecharge", "telecharger",
    "recupere", "recuperer", "trouve", "trouver", "cherche", "chercher", "recherche", "rechercher",
    "download", "find", "create", "generate", "make", "write", "export", "save", "build",
    "veux", "voudrais", "peux", "pourrais", "merci", "dans", "ici", "maintenant",
    # formats / contenants
    "fichier", "document", "word", "docx", "pdf", "latex", "tex", "html", "markdown", "md",
    "format", "version", "forme", "excel", "xlsx", "powerpoint", "pptx", "odt", "csv", "json",
    "svg", "page", "fiche",
}


def fold(text: str) -> str:
    """Minuscule + suppression des accents + espaces normalisés."""
    normalized = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().replace("’", "'").split())


@dataclass
class ArtifactRequest:
    """Résultat de l'analyse de la demande vis-à-vis des fichiers à produire."""

    wants_file: bool = False
    formats: list[str] = field(default_factory=list)
    mode: str = "none"  # none | generate | download | transcribe
    explicit_filenames: list[str] = field(default_factory=list)
    reproduce_from_image: bool = False
    subject: str = ""
    rationale: list[str] = field(default_factory=list)

    def allows(self, extension: str) -> bool:
        ext = extension.lower().lstrip(".")
        if ext in self.formats:
            return True
        return any(ext in INTERMEDIATE_FOR.get(fmt, set()) for fmt in self.formats)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detect_formats(folded: str) -> list[str]:
    found: list[str] = []
    for pattern, fmt in FORMAT_SYNONYMS:
        if re.search(pattern, folded) and fmt not in found:
            found.append(fmt)
    return found


def _explicit_filenames(raw: str) -> list[str]:
    names = re.findall(
        r"\b([A-Za-z0-9_\-À-ÿ]+\.(?:pdf|docx|doc|odt|rtf|tex|html?|md|xlsx|pptx|csv|json|svg|py|mmd|txt))\b",
        raw or "",
        re.IGNORECASE,
    )
    unique: list[str] = []
    for name in names:
        if name not in unique:
            unique.append(name)
    return unique


def detect_artifact_request(prompt: str, skill: str = "") -> ArtifactRequest:
    """Analyse la demande et indique si (et quel) fichier doit être produit."""
    raw = (prompt or "").strip()
    folded = fold(raw)
    req = ArtifactRequest()
    req.subject = extract_subject(raw)
    req.explicit_filenames = _explicit_filenames(raw)

    skill_name = (skill or "").lstrip("/").lower()
    slash = re.match(r"^/([a-z0-9_-]+)\b", folded)
    if slash and not skill_name:
        skill_name = slash.group(1)

    req.reproduce_from_image = bool(_REPRODUCE_IMAGE.search(folded))
    formats = _detect_formats(folded)
    has_create = bool(re.search(rf"\b(?:{_CREATE_VERBS})\b", folded))
    has_download = bool(re.search(rf"\b(?:{_DOWNLOAD_VERBS})\b", folded))
    has_format_phrase = bool(_FORMAT_PREPOSITION.search(folded))

    # 1. Skills éducatifs : leur contrat est de livrer un PDF compilé (source .tex incluse).
    if skill_name in _EDUCATION_SKILLS:
        req.wants_file = True
        req.mode = "generate"
        req.formats = ["pdf"]
        req.rationale.append(f"skill /{skill_name} : livrable PDF contractuel")
        return req

    # 2. Téléchargement Web explicite.
    if has_download:
        req.wants_file = True
        req.mode = "download"
        req.formats = [f for f in formats if f in DELIVERABLE_EXTENSIONS | {"csv", "json"}] or ["pdf"]
        req.rationale.append("verbe de téléchargement détecté : le fichier doit provenir du Web")
        return req

    # 3. Noms de fichiers explicites.
    if req.explicit_filenames:
        req.wants_file = True
        req.mode = "generate"
        for name in req.explicit_filenames:
            ext = PurePosixPath(name).suffix.lstrip(".").lower()
            ext = "html" if ext == "htm" else ext
            if ext not in req.formats:
                req.formats.append(ext)
        req.rationale.append("nom de fichier explicite dans la demande")
        return req

    # 4. Verbe de création + format, ou tournure "en PDF", "au format Word"...
    if formats and (has_create or has_format_phrase):
        req.wants_file = True
        req.mode = "transcribe" if req.reproduce_from_image else "generate"
        req.formats = formats
        req.rationale.append("verbe de création ou tournure de format explicite")
        return req

    # 5. Reproduction d'image sans format : réponse textuelle fidèle, aucun fichier.
    if req.reproduce_from_image:
        req.mode = "transcribe"
        req.rationale.append("transcription fidèle demandée sans format de fichier")
        return req

    req.rationale.append("aucune demande de fichier : explication / analyse / recherche")
    return req


def extract_subject(prompt: str) -> str:
    """Extrait les mots porteurs de sens (sans verbes de demande ni formats)."""
    folded = fold(prompt)
    folded = re.sub(r"^/[a-z0-9_-]+\s*", "", folded)
    folded = re.sub(r"\b[a-z0-9_-]+\.(?:pdf|docx|tex|html?|md|xlsx|pptx|csv|json|svg|py)\b", " ", folded)
    tokens = re.split(r"[^a-z0-9]+", folded)
    kept = [tok for tok in tokens if tok and tok not in _STOPWORDS and not (len(tok) == 1 and tok.isalpha())]
    return " ".join(kept[:6])


def suggest_filename(prompt: str, extension: str, *, content: str = "", fallback: str = "document") -> str:
    """Propose un nom de fichier adapté au contenu (ex. identites_remarquables.docx)."""
    ext = extension.lower().lstrip(".")
    for name in _explicit_filenames(prompt):
        if PurePosixPath(name).suffix.lstrip(".").lower() == ext:
            return name
    subject = extract_subject(prompt)
    if not subject and content:
        heading = re.search(r"^\s*#+\s*(.+)$|\\(?:title|section)\{([^}]+)\}", content, re.MULTILINE)
        if heading:
            subject = extract_subject(heading.group(1) or heading.group(2) or "")
    slug = "_".join(subject.split()[:5]).strip("_")
    slug = re.sub(r"_+", "_", slug)[:60].strip("_")
    return f"{slug or fallback}.{ext}"


def classify_origin(tool_result: dict[str, Any]) -> list[tuple[str, str]]:
    """Extrait (chemin, origine) des fichiers produits par un résultat d'outil."""
    tool = str(tool_result.get("tool") or "")
    data = tool_result.get("data") or {}
    if not isinstance(data, dict):
        return []
    produced: list[tuple[str, str]] = []

    def add(path: Any, origin: str) -> None:
        if isinstance(path, str) and path:
            produced.append((path.replace("\\", "/"), origin))

    if tool in {"download_resource", "download_via_browser", "web_search", "fetch_url"}:
        dl = data.get("downloaded_file")
        if isinstance(dl, dict):
            add(dl.get("relative_path") or dl.get("path"), "downloaded")
        add(data.get("saved_path"), "downloaded")
        if tool in {"download_resource", "download_via_browser"}:
            add(data.get("relative_path") or data.get("path"), "downloaded")
    elif tool in {"compile_document", "compile_latex"}:
        add(data.get("relative_path") or data.get("pdf_path"), "compiled")
    elif tool == "generate_docx":
        add(data.get("relative_path") or data.get("path"), "generated")
    elif tool in {"write_file", "patch_file", "move_file"}:
        add(data.get("path") or data.get("destination"), "generated")
    elif tool == "render_math_figure":
        add(data.get("pdf_relative_path") or data.get("pdf_path"), "compiled")
    return produced


def evaluate_artifacts(
    request: ArtifactRequest,
    produced: Iterable[tuple[str, str]],
) -> dict[str, Any]:
    """Compare demande -> artefact attendu -> artefact réellement produit.

    Retourne {"status": passed|failed|not_applicable, "evidence": str, "violations": [...]}.
    """
    deliverables = []
    for path, origin in produced:
        ext = PurePosixPath(path).suffix.lstrip(".").lower()
        ext = "html" if ext == "htm" else ext
        if ext in DELIVERABLE_EXTENSIONS or (request.wants_file and ext in request.formats):
            deliverables.append((path, origin, ext))

    if not request.wants_file and not deliverables:
        return {"status": "not_applicable", "evidence": "Aucun fichier demandé, aucun fichier produit.", "violations": []}

    violations: list[str] = []
    if not request.wants_file:
        for path, origin, _ in deliverables:
            violations.append(f"Fichier non demandé produit : {path} ({origin}).")
    else:
        for path, origin, ext in deliverables:
            if not request.allows(ext):
                violations.append(
                    f"Format non demandé : {path} (.{ext}) ; formats demandés : {', '.join(request.formats)}."
                )
            if request.mode == "download" and origin in {"generated", "compiled"} and ext in request.formats:
                violations.append(
                    f"Substitution interdite : {path} a été {('compilé' if origin == 'compiled' else 'généré')} "
                    "localement alors qu'un document distant devait être téléchargé."
                )
        final_exts = {ext for _, origin, ext in deliverables if ext in request.formats}
        if request.mode == "download":
            final_exts = {
                ext for _, origin, ext in deliverables if ext in request.formats and origin == "downloaded"
            }
        missing = [fmt for fmt in request.formats if fmt not in final_exts]
        if missing:
            violations.append("Format(s) demandé(s) non produit(s) : " + ", ".join(missing) + ".")

    if violations:
        return {"status": "failed", "evidence": " ".join(violations), "violations": violations}
    return {
        "status": "passed",
        "evidence": "Artefacts conformes à la demande : "
        + ", ".join(f"{p} ({o})" for p, o, _ in deliverables),
        "violations": [],
    }

