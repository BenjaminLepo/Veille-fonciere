"""Met à jour data.json du site GitHub Pages de la veille foncière, sans export complet de la base.

Usage :
  python3 -I maj_site.py data.json index.json [--patches DOSSIER] [--statuts statuts.json]

  data.json   : fichier publié du dépôt (lu puis réécrit).
  index.json  : liste [{"id": ..., "updatedAt": ...}] de TOUS les documents de la collection
                `fonciers` (relus après les écritures de la veille).
  --patches   : dossier de fichiers <id>.json, un par foncier créé ou modifié. Chaque fichier
                contient les champs à publier ; ils sont fusionnés dans l'entrée existante
                (ou créent l'entrée). Pour un nouveau foncier, donner tous les champs publics
                plus rang, taux, cible, manque, pm2Terrain de la commune (ref/communes).
  --statuts   : réponse JSON de Supabase export_statuts ; seul le statut est recopié.

Le script tient etat_site.json (id -> updatedAt publié) à côté de data.json.
Les champs privés (note, mailLien, majLe) ne sont jamais publiés.

Code de sortie : 0 si le site est à jour ; 2 s'il reste des fonciers à exporter (absents du site
ou modifiés dans la base depuis la dernière publication) : leurs id sont listés, écrire un patch
complet pour chacun puis relancer. data.json est écrit dans tous les cas.
"""
import argparse, glob, json, os, sys
from datetime import datetime, timezone, timedelta

PRIVES = {"note", "mailLien", "majLe", "id", "updatedAt", "version"}
PUBLICS = ["titre", "commune", "insee", "dep", "type", "surface", "habitable", "prix", "prixM2",
           "historiquePrix", "source", "url", "autresAnnonces", "dateAnnonce", "vuLe", "score",
           "scoreCommune", "statut", "pourquoi", "zonage", "rang", "taux", "cible", "manque", "pm2Terrain"]
ZONAGE = ("statut", "constructible", "zone", "zoneLong", "lat", "lon")
STATUTS = {"nouveau", "a_etudier", "contacte", "retenu", "ecarte"}


def lit(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def nettoie(d):
    if isinstance(d.get("data"), dict):          # format {id, data, version} accepté
        d = d["data"]
    x = {k: d[k] for k in PUBLICS if k in d and k not in PRIVES}
    if isinstance(x.get("zonage"), dict):
        z = x["zonage"]
        x["zonage"] = {k: z[k] for k in ZONAGE if z.get(k) is not None}
    return x


ap = argparse.ArgumentParser()
ap.add_argument("data"); ap.add_argument("index")
ap.add_argument("--patches"); ap.add_argument("--statuts")
a = ap.parse_args()

site = lit(a.data) if os.path.exists(a.data) else {"fonciers": []}
items = {f["id"]: f for f in site.get("fonciers", [])}
etat_path = os.path.join(os.path.dirname(os.path.abspath(a.data)), "etat_site.json")
premier = not os.path.exists(etat_path)
etat = {} if premier else lit(etat_path)

index = lit(a.index)
if isinstance(index, dict):
    index = index.get("fonciers") or index.get("items") or []
base = {r["id"]: r.get("updatedAt") for r in index}
if not base:
    sys.exit("index.json vide : relis la collection fonciers avant de publier.")
if premier:  # amorçage : on considère le site actuel comme à jour
    etat = {i: base[i] for i in items if i in base}

# 1. patches
patches = 0
if a.patches:
    for p in sorted(glob.glob(os.path.join(a.patches, "*.json"))):
        i = os.path.basename(p)[:-5]
        x = nettoie(lit(p))
        e = items.setdefault(i, {"id": i})
        e.update(x)
        if i in base:
            etat[i] = base[i]
        patches += 1

# 2. statuts saisis sur le site (Supabase)
synchro = 0
if a.statuts:
    for r in lit(a.statuts):
        e = items.get(r.get("id"))
        if e and r.get("statut") in STATUTS and e.get("statut") != r["statut"]:
            e["statut"] = r["statut"]; synchro += 1

# 3. cohérence avec la base
retires = [i for i in list(items) if i not in base]
for i in retires:
    del items[i]; etat.pop(i, None)
manquants = sorted(i for i in base if i not in items or "titre" not in items[i])
perimes = sorted(i for i in base if i in items and i not in manquants and etat.get(i) != base[i])
for i in manquants:
    items.pop(i, None)

paris = timezone(timedelta(hours=1))
out = {"maj": datetime.now(paris).strftime("%Y-%m-%dT%H:%M"),
       "fonciers": [items[i] for i in sorted(items)]}
txt = json.dumps(out, ensure_ascii=False, indent=1)
for k in ('"note"', '"mailLien"', '"majLe"'):
    if k in txt:
        sys.exit(f"Champ privé {k} détecté : rien n'est écrit.")
with open(a.data, "w", encoding="utf-8") as f:
    f.write(txt)
with open(etat_path, "w", encoding="utf-8") as f:
    json.dump(etat, f, ensure_ascii=False, indent=0, sort_keys=True)

print(f"{len(out['fonciers'])} fonciers publiés ({patches} patches, {synchro} statuts Supabase, "
      f"{len(retires)} retirés car absents de la base).")
if manquants or perimes:
    print("A EXPORTER (écrire un patch complet pour chacun puis relancer) :")
    print(json.dumps({"absents_du_site": manquants, "modifies_dans_la_base": perimes}, ensure_ascii=False))
    sys.exit(2)
print("Site cohérent avec la base.")
