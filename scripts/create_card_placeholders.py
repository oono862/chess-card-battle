"""
Create placeholder images for gimmick cards.
Generates:
 - images/card_death_1.png
 - images/card_kaiji_Jo.png
 - images/card_you_lose.gif
 - images/card_sh.png

Run: python scripts/create_card_placeholders.py
"""
import os
import base64

IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "images")
os.makedirs(IMG_DIR, exist_ok=True)

# 1x1 PNG (transparent)
png_b64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAA"
    "SUVORK5CYII="
)
# 1x1 GIF (transparent)
gif_b64 = "R0lGODdhAQABAPAAAP///wAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw=="

files = {
    "card_death_1.png": png_b64,
    "card_kaiji_Jo.png": png_b64,
    "card_you_lose.gif": gif_b64,
    "card_sh.png": png_b64,
}

for name, b64 in files.items():
    path = os.path.join(IMG_DIR, name)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    print("Wrote", path)

print("Placeholders created. Replace them with real art files as needed.")
