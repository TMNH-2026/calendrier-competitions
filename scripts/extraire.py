"""
Lit le PDF du calendrier de la ligue de tir Nord/Pas-de-Calais et en tire
une liste d'épreuves structurée (JSON).

Le PDF est un tableau à quatre colonnes : dates, championnats/matchs de
ligue, tournois/challenges, lieux. On s'appuie sur :
- les filets verticaux du tableau pour situer les colonnes ;
- la couleur de fond de la case « date » pour le niveau
  (vert = France, bleu = régional, jaune = départemental, orange = match) ;
- le texte rouge pour les dates limites ;
- des mots-clés pour les disciplines et l'École de tir.

Usage : python scripts/extraire.py calendrier.pdf sortie.json
"""
import datetime as dt
import json
import re
import sys
import unicodedata

import pymupdf

MOIS = {m: i + 1 for i, m in enumerate(
    "JANVIER FEVRIER MARS AVRIL MAI JUIN JUILLET AOUT SEPTEMBRE OCTOBRE NOVEMBRE DECEMBRE".split())}

NIVEAUX = {"france": "France", "regional": "Régional", "departemental": "Départemental",
           "match": "Match", "tournoi": "Tournoi / challenge"}
DISCIPLINES = {"c10": "Carabine 10 m", "p10": "Pistolet 10 m", "arb": "Arbalète", "c50": "Carabine 50 m",
               "p2550": "Pistolet 25/50 m", "rimfire": "RimFire", "tar": "Armes réglementaires (TAR)",
               "aa": "Armes anciennes", "silh": "Silhouettes métalliques", "c300": "300 m et ISR",
               "plateau": "Plateau (fosse olympique)", "nc": "Non précisée"}

NOTE_REGIONAL = ("Fin de la période des championnats régionaux : les classements nationaux "
                 "établis sur les scores régionaux seront bientôt publiés.")

# Lieux dont l'orthographe officielle ne se déduit pas des majuscules du PDF.
LIEUX = {
    "VILLENEUVE D'ASCQ": "Villeneuve-d'Ascq", "BULLY LES MINES": "Bully-les-Mines",
    "BILLY MONTIGNY": "Billy-Montigny", "SAINT OMER": "Saint-Omer",
    "SAINT MARTIN AU LAERT": "Saint-Martin-au-Laërt", "OYE PLAGE": "Oye-Plage",
    "CAPPELLE LA GRANDE": "Cappelle-la-Grande", "CHALONS EN CHAMPAGNE": "Châlons-en-Champagne",
    "BETHUNE": "Béthune", "CHATEAUROUX": "Châteauroux", "CNTS": "CNTS Châteauroux",
    "AULNOYE": "Aulnoye-Aymeries", "ZWEVEGEM": "Zwevegem (Belgique)",
    "TRITH ST LEGER": "Trith-Saint-Léger", "UTVA": "UTVA", "CTPN": "CTPN",
}
# Mots en capitales à qui rendre accents ou casse une fois le titre mis en minuscules.
MOTS = {
    "regionaux": "régionaux", "regional": "régional", "regionale": "régionale",
    "arbalete": "arbalète", "reglementaires": "réglementaires", "metalliques": "métalliques",
    "departemental": "départemental", "departementaux": "départementaux", "cote": "côte",
    "nord": "Nord", "rimfire": "RimFire", "cdfc": "CdFC", "edtir": "EdTir", "npdc": "NPdC",
    "ir900": "IR900", "isr": "ISR", "tar": "TAR", "france": "France", "avenir": "Avenir",
    "challenge": "Challenge", "pdc": "PdC",
}

COULEURS = [  # (r, g, b) approximatif -> niveau
    ((0.57, 0.82, 0.31), "france"),
    ((0.57, 0.80, 0.86), "regional"),
    ((1.00, 1.00, 0.00), "departemental"),
    ((1.00, 0.60, 0.40), "match"),
    ((0.97, 0.59, 0.28), "match"),
]


def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def niveau_couleur(fill):
    if not fill:
        return None
    best, dist = None, 1.0
    for rgb, niv in COULEURS:
        d = sum(abs(a - b) for a, b in zip(fill, rgb))
        if d < dist:
            best, dist = niv, d
    return best if dist < 0.2 else None


def en_capitales(s):
    lettres = [c for c in s if c.isalpha()]
    return lettres and sum(c.isupper() for c in lettres) / len(lettres) > 0.8


SIGLES = {"ISR", "TAR", "AA", "CNTS", "GS"}
PETITS_MOTS = {"DU", "DE", "LA", "LE", "ET", "EN", "AU", "DES", "AUX"}


def joli_mot(m):
    """Un mot en capitales redevient minuscule (accents rendus), sauf les sigles."""
    if m in PETITS_MOTS:
        return m.lower()
    if not m.isupper() or len(m) < 3 or re.search(r"[\d/]", m) or m in SIGLES:
        return m
    return MOTS.get(sans_accents(m.lower()), m.lower())


def joli_texte(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = " ".join(joli_mot(m) for m in s.split(" "))
    s = s[0].upper() + s[1:]
    s = re.sub(r"\bcote d'Opale", "Côte d'Opale", s, flags=re.I)
    s = re.sub(r"^Date limite des (?=championnats|régionaux)", "Clôture des ", s, flags=re.I)
    s = re.sub(r"^Date limite des envois", "Date limite d'envoi", s, flags=re.I)
    s = re.sub(r"(\d)\s?[mM]\b", r"\1 m", s)
    s = re.sub(r"(\d)(è|e)me\b", r"\1e", s)
    s = re.sub(r"(?<! du)\s+(\d+(?:er|e)) tou[rt]\b", r", \1 tour", s)
    s = re.sub(r"\bl'avenir\b", "l'Avenir", s)
    s = re.sub(r"\bEdTIR\b", "EdTir", s)
    s = re.sub(r"\bPas de Calais\b", "Pas-de-Calais", s)
    s = re.sub(r"^Rgx\b", "Régionaux", s)
    s = re.sub(r"^CdF\b", "Championnat de France", s)
    s = re.sub(r"\s*-\s*", " - ", s) if " - " in s else s
    return s.strip()


def joli_lieu(s):
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return ""
    cle = sans_accents(s).upper()
    if cle in LIEUX:
        return LIEUX[cle]
    return " ".join(w.capitalize() if w.isupper() else w for w in s.split(" "))


def disciplines(titre):
    s = " " + sans_accents(titre).upper().replace("-", " ") + " "
    d = []
    if "FOSSE" in s:
        d.append("plateau")
    if re.search(r"300 ?M|\bISR\b", s):
        d.append("c300")
    if "SILHOUETTE" in s:
        d.append("silh")
    if re.search(r"ARMES ANCIENNES|\bAA\b", s):
        d.append("aa")
    if re.search(r"\bTAR\b|ARMES REGLEMENTAIRES", s):
        d.append("tar")
    if "RIMFIRE" in s:
        d.append("rimfire")
    if d:
        return d
    if re.search(r"ARBALETE|\bAM ?10|\bAF ?18|IR900|18 ?M\b", s):
        d.append("arb")
    dix = re.search(r"\b10 ?M\b|\bC ?10|\bP ?10|\bAM ?10", s)
    edtir = re.search(r"EDTIR|AVENIR|JEUNES", s)
    if dix or (edtir and not re.search(r"25|50", s)):
        c = re.search(r"\bC ?10|CARABINE", s)
        p = re.search(r"\bP ?10|\bPV\b|PST|PISTOLET", s)
        if re.search(r"\bAM ?10", s) and not c and not p:
            pass
        else:
            if c or not p:
                d.append("c10")
            if p or not c:
                d.append("p10")
    trente_cinq = re.search(r"\b25\b|\b50\b|25 ?M|50 ?M|P25|25/50", s)
    if trente_cinq and not dix:
        c = "CARABINE" in s
        p = re.search(r"PISTOLET|\bP25|\bPST|VITESSE", s)
        generique = not c and not p
        if p or generique:
            d.append("p2550")
        if c or (generique and re.search(r"50", s)):
            d.append("c50")
    if "ARBALETE MATCH 30" in s and "arb" not in d:
        d.append("arb")
    return list(dict.fromkeys(d)) or ["nc"]


def est_ecole_de_tir(titre):
    return bool(re.search(r"EDTIR|AVENIR|JEUNES|ECOLES? DE TIR", sans_accents(titre).upper()))


def colonnes(page):
    xs = sorted({round(dr["rect"].x0) for dr in page.get_drawings()
                 if dr.get("fill") and dr["rect"].width < 3 and dr["rect"].height > 5})
    # Garder les filets principaux (écartés d'au moins 50 pt)
    principaux = []
    for x in xs:
        if not principaux or x - principaux[-1] > 50:
            principaux.append(x)
    if len(principaux) < 5:
        raise ValueError(f"colonnes introuvables ({principaux})")
    return principaux[:5]


def lignes(page):
    """Regroupe les segments de texte par ligne (même ordonnée à 2,5 pt près)."""
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip():
                    spans.append(s)
    spans.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))
    groupes = []
    for s in spans:
        y = s["bbox"][1]
        if groupes and abs(groupes[-1][0] - y) < 2.5:
            groupes[-1][1].append(s)
        else:
            groupes.append((y, [s]))
    return groupes


def remplissages(page, x_dates):
    rects = []
    for dr in page.get_drawings():
        f = dr.get("fill")
        r = dr["rect"]
        if f and abs(r.x0 - x_dates) < 4 and r.width > 50 and r.height > 5:
            rects.append((r, f))
    return rects


def extraire(chemin):
    doc = pymupdf.open(chemin)
    texte1 = doc[0].get_text()
    if "CALENDRIER" not in texte1.upper():
        raise ValueError("ce PDF ne ressemble pas au calendrier de la ligue")
    m = re.search(r"Saison\s+(\d{4})\s*/\s*(\d{4})", texte1)
    saison = f"{m.group(1)}-{m.group(2)}" if m else None
    m = re.search(r"au\s+(\d{1,2})/(\d{1,2})/(\d{4})", texte1)
    maj = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat() if m else None

    evts, anomalies = [], []
    mois_courant, mois_suivant, dernier = None, None, None

    for page in doc:
        cols = colonnes(page)
        x_champ, x_tournoi, x_lieu = cols[1], cols[2], cols[3]
        fills = remplissages(page, cols[0])
        groupes = lignes(page)
        dates_page = [(y, " ".join(s["text"] for s in ss if s["bbox"][2] < x_champ + 2)) for y, ss in groupes]

        for i, (y, ss) in enumerate(groupes):
            tout = " ".join(s["text"].strip() for s in ss)
            mm = re.fullmatch(r"([A-Z]+)(?: ET ([A-Z]+))? (\d{4})", sans_accents(tout).upper().strip())
            if mm and sans_accents(mm.group(1)) in MOIS:
                an = int(mm.group(3))
                mois_courant = (an, MOIS[mm.group(1)])
                mois_suivant = (an, MOIS[mm.group(2)]) if mm.group(2) in MOIS else None
                continue
            if mois_courant is None:
                continue
            date_txt = " ".join(s["text"] for s in ss if s["bbox"][2] < x_champ + 2).strip()
            lieu = " ".join(s["text"] for s in ss if s["bbox"][0] >= x_lieu - 1).strip()
            corps = [s for s in ss if s["bbox"][2] >= x_champ + 2 and s["bbox"][0] < x_lieu - 1]
            if not corps:
                continue
            titre_brut = " ".join(s["text"].strip() for s in corps)
            rouge = any(s["color"] == 0xFF0000 for s in corps)
            gauche = min(s["bbox"][0] for s in corps)
            col_champ = abs(gauche - x_champ) < 6

            a_preciser = False
            if not re.search(r"\d", date_txt):
                # Case date colorée mais vide : prendre la date de la ligne suivante.
                suiv = [d for yy, d in dates_page[i + 1:] if yy - y < 25 and re.search(r"\d", d)]
                if not suiv:
                    anomalies.append(f"sans date : {titre_brut}")
                    continue
                date_txt, a_preciser = suiv[0], True

            nums = [int(n) for n in re.findall(r"\d+", date_txt)]
            j1, j2 = nums[0], nums[-1]
            an, mo = mois_courant
            try:
                fin = dt.date(an, mo, j2)
                if mois_suivant and dernier and fin < dernier - dt.timedelta(days=3):
                    # En-tête « MAI et JUIN » : on est passé au second mois.
                    mois_courant, mois_suivant = mois_suivant, None
                    an, mo = mois_courant
                    fin = dt.date(an, mo, j2)
                if j1 > j2:
                    pa, pm = (an, mo - 1) if mo > 1 else (an - 1, 12)
                    debut = dt.date(pa, pm, j1)
                else:
                    debut = dt.date(an, mo, j1)
            except ValueError:
                anomalies.append(f"date illisible « {date_txt} » : {titre_brut}")
                continue
            dernier = debut

            ymid = y + 4
            fill = next((f for r, f in fills if r.y0 - 1 <= ymid <= r.y1 + 1 and f != (1.0, 1.0, 1.0)), None)
            niv = niveau_couleur(fill)
            limite = rouge or sans_accents(titre_brut).upper().startswith("DATE LIMITE")
            regional_lim = limite and "REGIONAUX" in sans_accents(titre_brut).upper()
            if limite:
                niv = "regional" if regional_lim else "tournoi"
            elif niv is None:
                niv = "match" if re.match(r"\s*(Match|France\s*-)", titre_brut, re.I) else "tournoi"

            titre = titre_brut
            lieu_txt = joli_lieu(lieu)
            zones = re.search(r"\(([^)]*)\)\s*$", titre)
            if "SUIVANT ZONES" in lieu.upper() and zones:
                clubs = [joli_lieu(c.strip()) for c in zones.group(1).split("/")]
                lieu_txt = "Suivant zones : " + " / ".join(clubs)
                titre = titre[:zones.start()]
            elif "SUIVANT ZONES" in lieu.upper():
                lieu_txt = "Suivant zones"

            e = {"debut": debut.isoformat()}
            if fin != debut:
                e["fin"] = fin.isoformat()
            e["niveau"] = niv
            e["titre"] = joli_texte(titre)
            if lieu_txt:
                e["lieu"] = lieu_txt
            e["disciplines"] = disciplines(titre_brut)
            if est_ecole_de_tir(titre_brut):
                e["ecoleDeTir"] = True
            if limite:
                e["type"] = "date-limite"
                if regional_lim:
                    e["note"] = NOTE_REGIONAL
            if a_preciser:
                e["dateAPreciser"] = True
            evts.append(e)

    evts.sort(key=lambda e: e["debut"])
    return {
        "source": "Ligue de tir Nord/Pas-de-Calais — calendrier prévisionnel des activités sportives"
                  + (f", saison {saison.replace('-', '/')}" if saison else "")
                  + (f" (à jour au {dt.date.fromisoformat(maj).strftime('%d/%m/%Y')})" if maj else ""),
        "saison": saison,
        "miseAJour": maj,
        "niveaux": NIVEAUX,
        "disciplines": DISCIPLINES,
        "evenements": evts,
    }, anomalies


def valider(data, precedent=None):
    """Renvoie la liste des problèmes qui doivent bloquer la publication."""
    pb = []
    ev = data["evenements"]
    if len(ev) < 40:
        pb.append(f"seulement {len(ev)} épreuves lues")
    if precedent and len(ev) < 0.6 * len(precedent.get("evenements", [])):
        pb.append(f"{len(ev)} épreuves contre {len(precedent['evenements'])} dans la version précédente")
    if not data.get("saison"):
        pb.append("saison introuvable dans le PDF")
    else:
        a1, a2 = map(int, data["saison"].split("-"))
        for e in ev:
            d = dt.date.fromisoformat(e["debut"])
            if not (dt.date(a1, 7, 1) <= d <= dt.date(a2, 10, 31)):
                pb.append(f"date hors saison : {e['debut']} {e['titre']}")
    nc = sum(e["disciplines"] == ["nc"] for e in ev)
    if ev and nc / len(ev) > 0.35:
        pb.append(f"{nc} épreuves sans discipline reconnue")
    return pb


if __name__ == "__main__":
    data, anomalies = extraire(sys.argv[1])
    json.dump(data, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(data['evenements'])} épreuves, saison {data['saison']}, à jour au {data['miseAJour']}")
    for a in anomalies:
        print("ANOMALIE :", a)
    for p in valider(data):
        print("PROBLÈME :", p)
