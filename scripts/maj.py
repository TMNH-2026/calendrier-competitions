"""
Mise à jour automatique du calendrier.

1. Lit la page de la ligue et y repère le PDF du calendrier le plus récent
   (le nom du fichier change à chaque version : on ne s'y fie pas).
2. Le télécharge et compare son empreinte avec celle déjà publiée.
3. S'il a changé : l'extrait, le contrôle, et écrit calendrier.json.

Code de sortie : 0 = à jour ou mis à jour ; 1 = problème (rien n'est publié).
Écrit dans $GITHUB_OUTPUT « change=oui|non » et « resume=… ».
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extraire import extraire, valider  # noqa: E402

PAGE = "https://www.liguedetirnpdc.fr/calendrier-gs/"
RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "calendrier.json"
SOURCE = RACINE / "source.json"
ENTETES = {"User-Agent": "Mozilla/5.0 (calendrier TMNH ; mise a jour hebdomadaire)"}


def telecharger(url):
    req = urllib.request.Request(url, headers=ENTETES)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def cle(url):
    """Plus la clé est grande, plus le PDF est probablement le calendrier en vigueur."""
    nom = urllib.parse.unquote(url.rsplit("/", 1)[-1]).upper()
    annees = [int(a) for a in re.findall(r"20\d\d", nom)] or [0]
    depot = re.search(r"/uploads/(\d{4})/(\d{2})/", url)
    version = [int(v) for v in re.findall(r"V\s?(\d+)", nom)] or [0]
    return (
        "CALENDRIER" in nom,
        bool(re.search(r"\bGS\b|[-_ ]GS[-_ .]", nom)),
        max(annees),
        (int(depot.group(1)), int(depot.group(2))) if depot else (0, 0),
        max(version),
    )


def trouver_pdf(html):
    liens = {urllib.parse.urljoin(PAGE, h) for h in
             re.findall(r"""href=["']([^"']+?\.pdf(?:\?[^"']*)?)["']""", html, re.I)}
    if not liens:
        raise RuntimeError(f"aucun PDF trouvé sur {PAGE}")
    return max(liens, key=cle), sorted(liens)


def sortie(**kv):
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a", encoding="utf-8") as o:
            for k, v in kv.items():
                o.write(f"{k}={v}\n")


def main():
    html = telecharger(PAGE).decode("utf-8", "replace")
    url, tous = trouver_pdf(html)
    print("PDF trouvés sur la page :", *tous, sep="\n  ")
    print("Retenu :", url)

    pdf = telecharger(url)
    empreinte = hashlib.sha256(pdf).hexdigest()
    ancienne = json.loads(SOURCE.read_text(encoding="utf-8")) if SOURCE.exists() else {}
    if ancienne.get("sha256") == empreinte:
        print("Calendrier inchangé.")
        sortie(change="non")
        return 0

    tmp = RACINE / "sources" / "dernier.pdf"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_bytes(pdf)
    data, anomalies = extraire(tmp)
    precedent = json.loads(DONNEES.read_text(encoding="utf-8")) if DONNEES.exists() else None
    problemes = valider(data, precedent)
    for a in anomalies:
        print("Anomalie :", a)
    if problemes:
        print("Publication bloquée :", *problemes, sep="\n  - ")
        sortie(change="non", resume=" ; ".join(problemes)[:900])
        return 1

    nom = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    data["pdf"] = url
    DONNEES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    SOURCE.write_text(json.dumps({
        "pdf": url, "fichier": nom, "sha256": empreinte,
        "recupereLe": dt.date.today().isoformat(), "miseAJourLigue": data.get("miseAJour"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.rename(tmp.with_name(nom if nom.lower().endswith(".pdf") else nom + ".pdf"))
    resume = f"{nom} : {len(data['evenements'])} épreuves (ligue à jour au {data.get('miseAJour')})"
    print("Mis à jour —", resume)
    sortie(change="oui", resume=resume)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # page inaccessible, PDF illisible…
        print("Échec :", e)
        sortie(change="non", resume=str(e)[:900])
        sys.exit(1)
