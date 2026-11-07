# Reproduire et auditer un bundle Android GSI

Cette version automatise l'inventaire, l'extraction gzip, les contrôles de bundle
et l'orchestration fastboot. **La transformation ext4 et l'adaptation du boot ne
sont pas encore automatisées dans ce dépôt.** Cette fiche décrit ce qui a été
fait, pour permettre un audit et une future automatisation sans recopier les
essais ratés. Un SHA256 de l'image dérivée n'est pas une recette de construction.

## 1. Vérifier le téléphone et préparer le retour stock

Lire `doctor`, comparer le modèle, la région du vendor et la configuration
effective. Le noyau peut annoncer `armv8l` via un processus 32 bits alors qu'il est
ARM64 : vérifier `CONFIG_ARM64=y`, `CONFIG_64BIT=y` et binder64 dans `/proc/config.gz`.
L'outil refuse une configuration inaccessible plutôt que de déduire le binder du CPU.

Obtenir le firmware **officiel exact**, vérifier sa provenance et ses manifestes
internes, conserver boot/vbmeta/super pour un retour logiciel. La restauration
réelle du téléphone de référence n'a pas été exécutée. Ne jamais lancer aveuglément
`flash_all.bat` : il peut écrire preloader ou relocker selon le script.
Ne pas utiliser un scatter téléchargé comme preuve de la GPT du téléphone.

Archive stock utilisée :
`dandelion_eea_global_images_V12.0.17.0.QCDEUXM_20220118.0000.00_10.0_eea_10174adb81.tgz`.
Taille 4 345 766 369 octets ; SHA256 :
`c7fa75f12dd479ef07cd1acf14d2afef1d7f3d425075c0aacc5c88b8d69456dc`.
Le checksum documente l'archive contrôlée ; il ne fournit pas une licence de redistribution.

## 2. Extraire la GSI et inspecter son contenu

Source de référence :
[Andy Yan, Lineage 20 TD](https://sourceforge.net/projects/andyyan-gsi/files/lineage-20-td/),
`lineage-20.0-20251021-UNOFFICIAL-a64_bvN.img.gz`.
Ne pas choisir le bouton « latest » sans contrôler l'architecture : il peut
viser arm64 ou une autre version.

Archive : 769 291 722 octets, SHA256
`62551575a4134813274ed2b255bc695523e8b5dd991b53269c7019227cb65e4e`.

```text
python -m redmi9a extract artifacts/lineage.img.gz artifacts/system-original.img --sha256 62551575a4134813274ed2b255bc695523e8b5dd991b53269c7019227cb65e4e --max-bytes 2281046016
python -m redmi9a inspect artifacts/system-original.img
```

L'image originale a le flag ext4 `shared_blocks` : `inspect` et l'étape finale
de `extract` le refuseront pour une installation directe. **L'extraction gzip
reste complète et conservée lorsque c'est cet audit final qui refuse l'image** ;
elle peut alors être préparée hors ligne. À l'inverse, une erreur gzip/CRC ou un
dépassement de taille supprime le fichier partiel.

Image originale : 1 649 119 232 octets ; SHA256
`d4ed044bcbfbb8352fb1dd8d2ec583f3bccf7181a06b99479723f8517325c733`.
Avec les outils ext4 Linux, vérifier sans montage en écriture : version Android,
ABI, propriétés, liens `/product`, applications incluses, intégrité e2fsck.
Cette source déclare Android13, Lineage20, correctif2025-09-05 et `ro.adb.secure=0`.

## 3. Produire une copie ext4 adaptée

Sur une copie distincte, jamais sur l'unique original :

- Agrandir le fichier puis le système ext4 à 2 Gio avec les outils ext4.
- Exécuter `e2fsck -E unshare_blocks` et traiter son résultat ; ne pas effacer
  simplement le flag `shared_blocks` pour faire disparaître l'alerte.
- Modifier uniquement `ro.adb.secure=0` en `ro.adb.secure=1` : trois occurrences
  dans `/system/build.prop`, une dans `/system/system_ext/etc/build.prop` dans
  **cette image précise**. Conserver modes, propriétaires et attributs SELinux.
- Le chantier l'a fait par modification de quatre octets aux blocs de données
  localisés avec `debugfs bmap`, après séparation des blocs partagés. Il faut
  recalculer les positions pour chaque construction, jamais réutiliser les offsets.
- Vérifier les quatre octets, les deux fichiers, les métadonnées et exécuter
  `e2fsck -fn` avec résultat0. Réinspecter les propriétés finales.

Image dérivée de référence : 2 147 483 648 octets ; SHA256 dans le bundle exemple.
Les métadonnées ext4 peuvent varier d'une construction à l'autre : un hash
différent exige un audit de la nouvelle construction, pas le remplacement
aveugle de la valeur attendue dans le manifeste.

## 4. Adapter le boot sans remplacer le noyau stock

Extraire le boot du firmware exact et inspecter son ramdisk avec les outils
[Magisk officiels](https://topjohnwu.github.io/Magisk/install.html).
La GSI fournit `/product` via `/system/product` ; le product MIUI ne doit pas
masquer ces composants. Dans le ramdisk stock, retirer uniquement la ligne
montant `product /product` de `fstab.mt6762` et `fstab.mt6765`, en conservant
leurs modes0640/root et toutes les entrées system/vendor/data.

Faire cette adaptation **avant** le patch Magisk afin que ses sauvegardes
internes et une réinstallation directe gardent les fstab adaptées. Le chantier
a utilisé Magisk31.1 sur le téléphone lui-même, avec :

```text
KEEPVERITY=false
KEEPFORCEENCRYPT=true
PATCHVBMETAFLAG=false
RECOVERYMODE=false
LEGACYSAR=false
```

Comparer les octets du noyau compressé au stock après reconstruction. Une
première reconstruction qui recompressait le noyau a été rejetée ; elle n'a
pas été flashée. Refaire le ramdisk sans recompression du noyau inchangé.
Relire les fstab finales et le boot pour constater le diff attendu.
Ne pas réutiliser une image Magisk d'un autre téléphone ou d'un autre firmware.
Une recette sans root aurait aussi besoin de conserver l'adaptation product.

## 5. Construire et examiner le manifeste

Copier l'exemple dans le répertoire privé des trois images locales. Renseigner
leurs véritables empreintes après audit et les propriétés Android attendues.
`audits` contient des **attestations de l'opérateur**, pas des signatures ni
des contrôles automatiques du contenu. Les seules écritures prévues sont
boot, vbmeta, system, puis la remise à zéro Android autorisée.

`plan` recalcule les empreintes et vérifie formats et tailles, mais ne monte pas
ext4 et ne valide pas le ramdisk à la place de l'opérateur. Sur le téléphone,
`install` vérifie l'identité, le déverrouillage et la capacité réelle avant toute
écriture. Les partitions vendor et product restent présentes et inchangées.

La commande `fastboot -w` peut annoncer qu'elle ne sait pas formater un type
raw après l'effacement ; cela doit être contrôlé au premier démarrage.
Ne jamais annoncer « installé et fonctionnel » sur le seul retour de fastboot.

## Références

- [Android : exigences GSI](https://developer.android.com/topic/generic-system-image)
- [AOSP : fastbootd](https://source.android.com/docs/core/architecture/bootloader/fastbootd)
- [MTKClient officiel](https://github.com/bkerler/mtkclient)
- [Magisk : installation officielle](https://topjohnwu.github.io/Magisk/install.html)
- [Lineage Aperture : alias Lens](https://github.com/LineageOS/android_packages_apps_Aperture/tree/lineage-20.0)
- [Termux : releases officielles](https://github.com/termux/termux-app/releases)
