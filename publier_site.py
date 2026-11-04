"""Construit data.json du site GitHub Pages de la veille foncière.

Usage : python3 publier_site.py <dossier_export_fonciers> <communes.json> <sortie_data.json>
  dossier_export_fonciers : fichiers JSON écrits par ArtifactData list fonciers (out_dir)
  communes.json           : document ref/communes exporté (out_dir)
Les champs privés (note, mailLien, majLe) ne sont jamais publiés.
"""
import glob, json, os, sys
from datetime import datetime, timezone, timedelta

PRIVES = {"note", "mailLien", "majLe"}
GARDES = ["titre", "commune", "insee", "dep", "type", "surface", "habitable", "prix", "prixM2",
          "historiquePrix", "source", "url", "autresAnnonces", "dateAnnonce", "vuLe", "score",
          "scoreCommune", "statut", "pourquoi", "zonage"]

def charge(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d.get("data"), dict) and ("titre" in d["data"] or "communes" in d["data"]):
        return d["data"]
    return d

src, communes_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
ref = charge(communes_path).get("communes", [])
rangs = {c["insee"]: c for c in ref}
items = []
for f in sorted(glob.glob(os.path.join(src, "**", "*.json"), recursive=True)):
    d = charge(f)
    if "titre" not in d:
        continue
    x = {k: d.get(k) for k in GARDES if k in d and k not in PRIVES}
    x["id"] = os.path.basename(f)[:-5]
    c = rangs.get(d.get("insee") or "")
    if c:
        x["rang"] = c.get("rang"); x["taux"] = c.get("taux"); x["cible"] = c.get("cible")
        x["manque"] = c.get("manque"); x["pm2Terrain"] = c.get("pm2Terrain")
    if isinstance(x.get("zonage"), dict):
        z = x["zonage"]
        x["zonage"] = {k: z.get(k) for k in ("statut", "constructible", "zone", "zoneLong", "lat", "lon") if z.get(k) is not None}
    items.append(x)
paris = timezone(timedelta(hours=1))
json.dump({"maj": datetime.now(paris).strftime("%Y-%m-%dT%H:%M"), "fonciers": items},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(items)} fonciers écrits dans {out}")
