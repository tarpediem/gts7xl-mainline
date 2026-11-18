# Porter Linux mainline sur un appareil Samsung : retour d'expérience

Ce guide raconte comment on a porté Linux mainline sur une Galaxy Tab S7+ 5G (SM-T976B,
Snapdragon 865), de la tablette Android jusqu'à un Omarchy (Arch Linux ARM) avec GNOME,
GPU, son, charge, S Pen et capteurs. Il est écrit pour quelqu'un qui veut refaire la même
chose sur un autre Samsung, par exemple un **Galaxy S5**.

Le dépôt complet (outils, runbooks, notes) : https://github.com/tarpediem/gts7xl-mainline

---

## 0. Avant tout : le Galaxy S5 part de beaucoup plus loin que nous

Le Galaxy S5 n'est pas un seul téléphone :

| Modèle | Nom de code | Puce | Mainline |
|---|---|---|---|
| SM-G900F / G900I / G900T / G900W8… | `klte` (et variantes) | Qualcomm Snapdragon 801 (MSM8974AC) | **Déjà bien supporté** |
| SM-G900H | `k3g` | Samsung Exynos 5422 | Peu ou pas supporté |

Vérifie le modèle exact dans *Paramètres → À propos* ou sous la batterie.

Pour un **klte**, ne refais pas notre travail : le MSM8974 est une des puces Qualcomm les
mieux supportées en mainline. postmarketOS a un port `samsung-klte` avec device tree en
mainline (écran, tactile, Wi-Fi, USB, batterie, GPU Adreno 330 via freedreno…).
Commence par :

- le wiki postmarketOS : https://wiki.postmarketos.org/wiki/Samsung_Galaxy_S5_(samsung-klte)
- le device tree déjà présent dans le noyau : `arch/arm/boot/dts/qcom/qcom-msm8974pro-samsung-klte.dts`

Le S5 est en **ARM 32 bits** côté mainline (armv7). Ça change le choix de la distribution
(voir §9). Ce guide reste utile pour la méthode, les pièges et ce qui manquera encore.

---

## 1. Ce qu'il faut avoir

- **Bootloader déverrouillable.** Les modèles US opérateur (Verizon, AT&T) sont souvent
  verrouillés pour de bon. Le déverrouillage grille Knox (définitif) et efface les données.
- **Un PC Linux** avec `heimdall` (flash Samsung), `pmbootstrap`, `dtc`, `adb`/`fastboot`
  si besoin, `python3`, et de la place (le noyau compilé prend plusieurs Go).
- **Un câble USB fiable.** C'est ton seul lien pendant des heures (flash, shell, réseau).
- **Du temps et de la patience** : sur la tablette, deux jours pleins pour arriver à une
  interface graphique, et encore plusieurs pour le son, les capteurs et le stylet.

## 2. Règles de sécurité qu'on s'est imposées (et qui nous ont sauvés)

1. **Sauvegarde EFS / modem avant toute chose.** Les partitions `efs`, `sec_efs`,
   `modemst1/2`, `fsg`, `persist` contiennent l'IMEI, les adresses MAC et les étalonnages
   d'usine. Une fois effacées, impossible de les recréer. On les a lues en `dd` avec root
   (Magisk) sous Android, avec des empreintes SHA256. **Ne jamais partager ces fichiers** (IMEI).
2. **N'écrire que ce qu'on sait remettre** : chez nous seulement `RECOVERY`, `BOOT`,
   `USERDATA` (et `VBMETA` si nécessaire). Jamais le bootloader, l'EFS ou le modem.
   La recovery d'origine est gardée pour revenir sous Android.
3. **Garder une voie de retour à chaque étape** : on flashe d'abord RECOVERY (Android reste
   intact dans BOOT), et quand Linux est installé, on garde une version qui marche dans
   RECOVERY pendant qu'on teste la suivante dans BOOT.
4. **Pas d'écriture directe dans les registres du PMIC** (la puce de gestion d'énergie). On
   ne passe que par les pilotes. Une mauvaise tension peut abîmer le matériel.
5. **Batterie : prudence absolue.** Le pilote de charge a été relu par un second regard
   indépendant, avec des limites **sous** celles de Samsung, un arrêt vérifié sur le
   matériel (le courant de la batterie doit vraiment tomber à zéro), une fenêtre de
   température et un minuteur.

## 3. Récupérer les infos du système d'origine

Tout part de ce que fait Android. On a tout relevé **pendant que One UI tournait** :

- Le **device tree réel** en mémoire (`/sys/firmware/fdt`), la ligne de commande du noyau,
  `dmesg`, `/proc/iomem`, la liste des bus I2C/SPI et des partitions.
- Les **sources du noyau Samsung** (opensource.samsung.com) : indispensables pour connaître
  les puces, leurs adresses, leurs GPIO et leurs tensions.
- Le **firmware d'origine** (les .tar Odin) : on y a trouvé les firmwares signés dont Linux
  a besoin (GPU, DSP audio, DSP des capteurs) dans `NON-HLOS.bin` et la partition vendor.
  Ces fichiers sont propriétaires : on les garde en local, **jamais sur GitHub**.

Pour le S5, le travail équivalent existe en grande partie dans postmarketOS.

## 4. Démarrer un noyau mainline sur un bootloader Samsung (ABL)

Le bootloader Samsung ne démarre pas n'importe quoi. Ce qui a marché chez nous (Snapdragon
865, bootloader ABL Android 10+) :

- Une image de boot au format Android, signée « à la Samsung » : on garde le pied de
  page AVB d'origine et on ajoute la mention `SEANDROIDENFORCE` à la fin. Avec le
  bootloader déverrouillé, il démarre l'image (écran d'avertissement orange).
- Un petit **shim** : le bootloader s'attend au device tree de Samsung. Le shim recopie la
  mémoire, la ligne de commande et l'initramfs calculées par le bootloader dans le device
  tree mainline, puis lance le noyau mainline.
- `vbmeta` désactivé, et le `dtbo` d'origine laissé tel quel (sinon Android ne redémarre plus).

Le S5 a un bootloader plus ancien (aboot, Android 4–6) : le chemin est différent et déjà
documenté par postmarketOS (souvent via `lk2nd`, un second bootloader qui simplifie tout).

## 5. La boucle de développement qui change tout : kexec

Reflasher pour chaque essai est lent et risqué. Une fois un premier noyau démarré, on a mis
en place **kexec** : depuis Linux sur l'appareil, on charge un nouveau noyau en RAM et on
saute dedans, sans flasher. Un essai prend une minute au lieu de dix, et un plantage se
répare d'un simple redémarrage.

Pièges rencontrés :
- un plantage au saut, lié à la sécurité CFI du noyau (fonction `machine_kexec` à marquer `__nocfi`) ;
- le saut tué par la déconnexion du shell : le lancer détaché (`setsid`, ignorer `HUP`) ;
- des périphériques laissés dans un état bizarre par le noyau précédent (DMA, DSP audio) :
  il faut parfois des correctifs pour les réinitialiser, ou désactiver ce qui ne sert pas ;
- les modules : un noyau recompilé ne charge pas les modules d'un autre build, même s'il a
  le même numéro de version. Chaque version a donc son propre dossier de modules.

## 6. L'ordre dans lequel on a réveillé le matériel

| Étape | Ce qui a coincé | Leçon |
|---|---|---|
| Écran | écran blanc puis noir : l'alimentation de l'écran coupée par le noyau | garder les alimentations allumées au début (`regulator_ignore_unused`), écrire un pilote de dalle (ici DSC, mode vidéo) |
| Tactile | le contrôleur d'I2C avait besoin du DMA GPI, avec un décalage de registre propre à ce SoC | lire le device tree d'origine ligne par ligne |
| Démarrage en boucle | une tension de régulateur hors de la grille autorisée faisait échouer **tout** le PMIC | une seule valeur fausse casse tout : respecter les pas de tension |
| USB réseau | ok | le shell par USB (`telnet 172.16.42.1` sous pmOS) est le meilleur ami |
| Wi-Fi / Bluetooth | firmware Qualcomm, adresse MAC à fixer | l'adresse MAC peut changer à chaque démarrage, la fixer dans NetworkManager |
| Système sur USERDATA | ok | `pmbootstrap` construit une image, on l'écrit dans USERDATA par USB |
| Charge | puce de charge reconnue seulement en révision 3, la nôtre était en « MD15 révision 2 » | comparer avec la table du pilote Samsung avant d'accepter une puce |
| GPU | firmware « zap » signé par Samsung, caché dans `NON-HLOS.bin` | sans lui, pas de GPU |
| Son | DSP audio + 4 amplis Cirrus CS35L41 ; gauche/droite inversées ; silence en 24 bits | tester ampli par ampli à faible volume, demander qui entend quoi |
| Capteurs | tout passe par le DSP des capteurs (SLPI) via `hexagonrpcd` + `libssc` | reprendre l'étalonnage d'usine depuis la partition persist |
| S Pen | puce Wacom W9021 avec le protocole de Samsung, pas celui du pilote mainline | un petit pilote dédié |

## 7. Pièges qui nous ont coûté cher

- **Les montages du PC.** Un script qui fabrique un chroot avec des montages « partagés »
  a démonté, en se nettoyant, les montages système du PC (`/sys/fs/cgroup`, `/dev/pts`…) :
  plus aucune appli ne se lançait. Désormais : tout chroot ou `pmbootstrap` dans un espace
  de montage privé (`sudo unshare --mount --propagation private -- …`), et jamais de
  `umount -l` sur un arbre partagé.
- **Le nettoyage automatique des modules** de certaines distributions efface les dossiers
  des noyaux qu'elles ne gèrent pas : plus de Wi-Fi au démarrage suivant. À désactiver.
- **Les dépôts mélangés.** Installer des paquets depuis un miroir plus récent que celui de la
  distribution laisse le système à moitié à jour (une mise à jour d'openssl allait casser
  `sudo`). Toujours faire des mises à jour complètes depuis les miroirs de la distribution.
- **Le volume des haut-parleurs.** Sans le firmware de protection de Samsung, les amplis
  peuvent saturer et abîmer les haut-parleurs : plafonner le volume et couper les basses
  en attendant.
- **Le courant de charge.** Un chargeur USB-C de 100 W reste en 5 V tant que personne ne
  négocie l'USB Power Delivery. On lit l'annonce Type-C (3 A) pour aller plus vite, sans
  dépasser les valeurs de Samsung.

## 8. Méthode de travail

- **Petites étapes, une chose à la fois**, et un test sur l'appareil après chacune.
- **Tout noter** (`NOTES.md`) : chaque flash, chaque valeur, chaque retour arrière possible.
- **Comparer à la source** : chaque tension, chaque courant, chaque GPIO doit venir du device
  tree ou du pilote de Samsung, avec la référence notée.
- **Des tests automatiques** pour les valeurs sensibles (par exemple : aucune limite de
  charge au-dessus de celles de Samsung).
- **Ne rien publier d'identifiant** : dépôts publics sans nom, IP, adresses MAC, numéro de
  série, IMEI, ni firmware propriétaire.

## 9. Le système au-dessus

On a utilisé **postmarketOS** pour faire marcher le matériel, puis on a remplacé le système
par **Omarchy** (Arch Linux ARM, 64 bits) avec GNOME pour le tactile, en gardant notre noyau.
Le noyau et le démarrage ne dépendent pas du système installé : changer de distribution,
c'est juste écrire une autre image dans USERDATA.

Pour le **S5 (32 bits)** : postmarketOS (Alpine) reste le meilleur choix, avec Phosh ou
Plasma Mobile pour un téléphone, ou une interface légère. Omarchy et beaucoup de distributions
modernes n'existent plus qu'en 64 bits.

## 10. Ce qui reste à faire chez nous

Veille (suspend), caméras (une sur trois a un pilote), micros, USB hôte (OTG), sortie vidéo
par l'USB-C et charge rapide en 9 V (il faut un pilote USB-C/PD pour la puce MAX77705),
et l'envoi des correctifs au noyau Linux officiel.

## Liens utiles

- Notre dépôt : https://github.com/tarpediem/gts7xl-mainline (runbooks dans `docs/runbooks/`)
- Notre noyau : https://github.com/tarpediem/gts7xl-linux · paquets : https://github.com/tarpediem/gts7xl-pmaports
- postmarketOS, porter un appareil : https://wiki.postmarketos.org/wiki/Porting_to_a_new_device
- Linux sur Qualcomm (projet linux-msm) : https://github.com/msm8916-mainline et https://github.com/linux-msm
- freedreno (GPU Adreno) : https://docs.mesa3d.org/drivers/freedreno.html
