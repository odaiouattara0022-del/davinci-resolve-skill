"""Génère les icônes PNG de MonBudget (sans dépendance externe)."""
import struct, zlib

FOND = (14, 110, 91)        # vert profond
BARRE = (220, 236, 230)     # vert pâle
BARRE_HAUTE = (255, 255, 255)


def png(chemin, taille):
    """Carré vert avec trois barres croissantes : le budget qui se remplit."""
    pixels = bytearray()
    marge = taille * 0.2
    largeur_barre = (taille - 2 * marge) / 5      # 3 barres + 2 espaces
    hauteurs = [0.38, 0.62, 0.9]
    bas = taille - marge
    rayon_barre = largeur_barre / 2

    barres = []
    for index, part in enumerate(hauteurs):
        gauche = marge + index * largeur_barre * 1.5
        haut = bas - (taille - 2 * marge) * part
        couleur = BARRE_HAUTE if index == 2 else BARRE
        barres.append((gauche, gauche + largeur_barre, haut, bas, couleur, rayon_barre))

    for y in range(taille):
        pixels.append(0)  # filtre de ligne
        for x in range(taille):
            couleur = FOND
            for gauche, droite, haut, bas_b, teinte, rayon in barres:
                if gauche <= x + 0.5 <= droite and haut <= y + 0.5 <= bas_b:
                    # coins arrondis en haut de chaque barre
                    cx = min(max(x + 0.5, gauche + rayon), droite - rayon)
                    cy = haut + rayon
                    if y + 0.5 < cy and (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 > rayon ** 2:
                        continue
                    couleur = teinte
                    break
            pixels.extend(couleur)

    def morceau(nom, donnees):
        return (struct.pack(">I", len(donnees)) + nom + donnees
                + struct.pack(">I", zlib.crc32(nom + donnees) & 0xFFFFFFFF))

    entete = struct.pack(">IIBBBBB", taille, taille, 8, 2, 0, 0, 0)
    contenu = (b"\x89PNG\r\n\x1a\n" + morceau(b"IHDR", entete)
               + morceau(b"IDAT", zlib.compress(bytes(pixels), 9)) + morceau(b"IEND", b""))
    with open(chemin, "wb") as fichier:
        fichier.write(contenu)
    print(chemin, len(contenu), "octets")


png("icone-180.png", 180)
png("icone-512.png", 512)
