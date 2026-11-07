# Redmi 9A Community Toolkit

Un outil communautaire pour préparer une seconde vie au Redmi 9A : diagnostic,
déverrouillage MediaTek encadré, contrôle des images, plan d'installation GSI et
vérification après démarrage. Python 3.10+, sans dépendance pour les commandes
Android/fastboot ; dépendances optionnelles pour MediaTek.

**Version expérimentale 0.1.** La procédure manuelle de référence a fonctionné
sur un Redmi 9A. Le diagnostic du nouvel outil a été exécuté sur ce téléphone.
Les nouvelles commandes d'écriture ont été testées avec des transports simulés,
**pas encore de bout en bout sur un téléphone de test**. Ne pas confondre ces états.

[English overview](docs/README.en.md) · [Procédure et préparation des images](docs/REPRODUCE.md)
· [Déverrouillage](docs/UNLOCK.md) · [Validation réelle](docs/VALIDATED_DEVICE.md)

## Compatibilité actuelle

| Élément | Périmètre |
|---|---|
| Appareil de référence | Redmi 9A M2006C3LG, dandelion, 2 Go / 32 Go |
| Vendor conservé | MIUI EEA V12.0.17.0.QCDEUXM, Android 10 |
| Système validé manuellement | LineageOS 20 / Android 13, GSI `a64_bvN`, Vanilla |
| Architecture | Android ARM32 + noyau ARM64 + binder64 + system-as-root |
| Hôtes visés | Windows, Linux, macOS ; matériel réellement vérifié depuis Windows |
| Déverrouillage automatisé | Adaptateur BROM/XFlash limité au CPU et à la GPT de référence |
| Autres firmwares, modèles, OS | Nécessitent profils, audit des images et validations supplémentaires |

`a64` ne veut pas dire GSI `arm64`. L'identifiant dandelion seul ne garantit pas
une révision matérielle compatible. Le programme refuse les écarts connus.
Linux natif demande un portage : les pilotes ne s'installent pas automatiquement
comme sur un PC. Le [port Droidian dandelion](https://github.com/droidian-mt6765/droidian-images-dandelion)
annonce avoir retiré ses images à cause de blocages sur certaines révisions.

## Démarrer par une lecture seule

Installer les [Android SDK Platform Tools officiels](https://developer.android.com/tools/releases/platform-tools),
Python 3.10+ et Git, puis placer `adb` et `fastboot` dans le PATH. Activer le
débogage USB et accepter normalement la confiance du PC sur le téléphone.

```text
git clone https://github.com/kinowill/redmi9a-toolkit.git
cd redmi9a-toolkit
python -m redmi9a doctor
python -m redmi9a verify
```

Le paquet peut aussi être installé dans un environnement Python isolé avec
`python -m pip install -e .`. Pour préciser les outils :

```text
python -m redmi9a --adb /path/to/adb --fastboot /path/to/fastboot doctor
python -m redmi9a --output work/doctor.json doctor
python -m redmi9a verify --root-check
```

Les options globales précèdent la commande. `--serial` permet de choisir un seul
téléphone ; son numéro ne figure pas dans les rapports. Les rapports restent
locaux, dans un répertoire ignoré par Git. L'outil ne transmet aucune télémétrie.

## Ce que font les commandes

| Commande | Effet |
|---|---|
| `doctor` | Lit identité, vendor, ABI, configuration ARM64/binder64, batterie, ADB et SELinux |
| `inspect image.img` | Détecte le format, vérifie quelques structures et calcule SHA256 ; pas un audit complet |
| `extract archive.gz image.img --sha256 …` | Vérifie empreinte et CRC, plafonne l'extraction, refuse l'écrasement |
| `unlock …` | Déverrouille le bootloader via l'adaptateur MediaTek dédié, avec consentement explicite |
| `plan artifacts/bundle.json` | Vérifie les fichiers locaux et affiche les étapes ; aucune commande téléphone |
| `install artifacts/bundle.json …` | Installe boot/vbmeta/system puis efface les données Android |
| `verify --bundle artifacts/bundle.json` | Vérifie le démarrage et la version attendue, sans supposer les fonctions matérielles |

Le [déverrouillage](docs/UNLOCK.md) est une étape séparée : téléphone identifié
sous Android avant connexion manuelle en BROM, dépendances et pilote nécessaires.
Si l'appareil compatible est déjà déverrouillé, aucune écriture MediaTek n'est faite.

## Installation : seulement après préparation et audit

**Déverrouiller et installer peuvent effacer les données et bloquer le téléphone.
Sauvegarder ce qui compte et préparer un retour au firmware exact avant d'écrire.**

Aucune image de ROM, APK, firmware, clé ADB ou sauvegarde d'appareil n'est fournie.
Préparer son propre boot adapté et ses images suivant le [guide](docs/REPRODUCE.md).
Copier `examples/bundle.example.json` dans `artifacts/bundle.json` et placer les
images dans ce même répertoire. Les empreintes de l'exemple documentent notre
construction, elles ne garantissent pas celles d'une nouvelle construction.

```text
python -m redmi9a plan artifacts/bundle.json
python -m redmi9a install artifacts/bundle.json --erase-userdata --confirm WIPE-DANDELION --journal work/install-001.json
```

Chaque écart arrête la procédure. Le programme vérifie fastbootd et la capacité
de system **avant la première écriture**, puis recontrôle lors des transitions.
Il ne redimensionne pas les partitions, n'écrit pas preloader/RPMB/vendor/product
et ne relance jamais automatiquement un flash en échec. Un journal existant
empêche une répétition accidentelle. Une écriture réussie ne prouve pas le démarrage.

Après configuration Android et autorisation USB normale :

```text
python -m redmi9a verify --bundle artifacts/bundle.json --root-check
```

Tester ensuite manuellement appels, données mobiles, Wi-Fi, Bluetooth, caméras,
audio, GPS, veille et redémarrage. Certaines étapes demandent une action physique
ou une confirmation du système : elles ne sont pas contournées.

## Sécurité et contribution

Le téléphone de référence reste rooté avec Magisk. Il a ADB authentifié,
SELinux Enforcing et chiffrement fichier actif ; ses composants Xiaomi sont
anciens. **Cette installation ne constitue pas un téléphone à jour en sécurité.**
Ne jamais relocker automatiquement le bootloader avec ces images personnalisées.

Les profils et bundles sont extensibles, mais déclarer `audits: true` ne vérifie
pas le contenu des images. L'outil refuse des erreurs communes ; il ne certifie
pas la sécurité d'une ROM. Lire [SECURITY.md](SECURITY.md) et [CONTRIBUTING.md](CONTRIBUTING.md).

Licence GPL-3.0-or-later pour ce code original. MTKClient, Magisk, LineageOS,
Termux et les outils Android restent des projets indépendants avec leurs
propres auteurs et licences. Aucun de leurs binaires n'est redistribué ici.
