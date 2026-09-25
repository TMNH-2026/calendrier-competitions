# Calendrier des compétitions de la ligue

Calendrier prévisionnel de la ligue de tir Nord/Pas-de-Calais, filtrable par
catégorie, type d'épreuve et discipline. Mis en forme par le Tir Métropole
Nord Haubourdin.

Page publique : https://calendrier.tmnh.fr/

Le fichier `CNAME` porte ce sous-domaine (entrée CNAME chez OVH vers
`tmnh-2026.github.io.`). Il doit rester sur `main` : le robot republie
`main` sur `gh-pages`.

## Mise à jour automatique

Chaque lundi matin, le robot `.github/workflows/maj-calendrier.yml` :

1. lit la page https://www.liguedetirnpdc.fr/calendrier-gs/ et retient le PDF
   « calendrier » le plus récent (saison, puis date de dépôt, puis n° de
   version) : le nom du fichier peut changer d'une version à l'autre ;
2. compare son empreinte avec `source.json` : si le fichier est le même, il
   s'arrête ;
3. sinon, il lit le PDF (`scripts/extraire.py`), contrôle le résultat et
   publie `calendrier.json`. Le PDF est archivé dans `sources/`.

Si la lecture ou le contrôle échoue, rien n'est publié et un ticket
(onglet *Issues*) signale le problème.

Pour lancer une vérification sans attendre lundi : onglet *Actions* >
« Mise à jour du calendrier » > *Run workflow*.

## Fichiers

- `index.html` : la page (aucune dépendance hors Google Fonts).
- `calendrier.json` : les données affichées. La version 4 a été saisie et
  relue à la main ; les suivantes sont extraites automatiquement.
- `source.json` : le PDF d'origine et son empreinte.
- `scripts/` : lecture du PDF et mise à jour.

Tester la lecture d'un PDF en local :

    pip install pymupdf
    python scripts/extraire.py calendrier.pdf sortie.json

Page marquée `noindex` : la version destinée au référencement sera celle du
futur site tmnh.fr.
