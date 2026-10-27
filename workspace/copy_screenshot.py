import os
import shutil

src = "screenshots/capture_bureau_demandee_1793115441405.png"
desktop = os.path.join(os.path.expanduser("~"), "Desktop")
dst = os.path.join(desktop, "capture_ecran_actuel.png")
shutil.copy(src, dst)
print(f"Copié avec succès vers {dst}")
