# Déverrouillage intégré : MediaTek/BROM, expérimental

La commande est une adaptation du chemin seccfg utilisé avec succès dans le
chantier de référence. **Le nouvel adaptateur n'a pas encore été exécuté de bout
en bout sur du matériel verrouillé.** Ses contrôles d'écriture et de relecture
sont testés avec une simulation de DA. L'appareil de référence est déjà déverrouillé :
le reverrouiller pour tester serait une mauvaise validation avec une ROM custom.

Ce module concerne uniquement le bootloader d'un appareil dont on est propriétaire.
Il ne retire aucun compte Xiaomi/Google, FRP, écran de verrouillage ou activation.
Déconnecter normalement ses comptes, sauvegarder ses données et activer
« Déverrouillage OEM » soi-même avant toute tentative. La voie officielle
Xiaomi Mi Unlock reste une alternative ; ses exigences ne sont pas supprimées.

## Préparer les dépendances

Utiliser un environnement Python isolé, le dépôt officiel MTKClient figé et
le preloader extrait du firmware exact. **Le fichier preloader sert à initialiser
la RAM via le DA ; aucune écriture de la partition preloader n'est autorisée.**

```text
python -m pip install -e ".[mtk]"
git clone https://github.com/bkerler/mtkclient.git artifacts/mtkclient
git -C artifacts/mtkclient checkout 118a000a83ea31c4f427fe5225abfe964546e05e
```

Le dossier MTKClient doit rester sans modification de fichiers suivis.
Les pilotes viennent de sources officielles :
[MTKClient](https://github.com/bkerler/mtkclient),
[UsbDk](https://github.com/daynix/UsbDk/releases),
[libusb](https://libusb.info/). Sous Windows, l'adaptateur choisit UsbDk et la
bibliothèque fournie par le dépôt MTKClient. Les confirmations administrateur
du système restent nécessaires. Il n'installe pas de pilote tout seul.

Le preloader de référence `preloader_k62v1_64_bsp.bin` doit avoir ce SHA256 :

```text
c0dfa5d13d88f03aeee4a2a4af943175cdc755cdadf5a96c20f16f83e1035cc4
```

## Lancer

Brancher d'abord le téléphone **allumé sous Android**, débogage USB autorisé.
L'outil lit modèle, vendor, ABI, configuration du noyau, batterie, état OEM et
sécurité ADB/SELinux avant toute connexion MediaTek.

```text
python -m redmi9a unlock --mtkclient artifacts/mtkclient --preloader artifacts/preloader_k62v1_64_bsp.bin --work-dir work/unlock-001 --accept-data-loss --confirm UNLOCK-DANDELION
```

Puis suivre le message : débrancher, éteindre, maintenir les deux volumes et
rebrancher pour présenter BROM. Ne pas maintenir Power indéfiniment. Une icône
de charge ou un périphérique HID ne constitue pas un dialogue BROM valide.
L'adaptateur attend au maximum 180 secondes puis s'arrête, sans nouvelle tentative.

## Contrôles et limites

1. Révision MTKClient et preloader exacts, session de travail neuve.
2. Identification BROM fraîche, matériel `0x766`, refus d'une session DA réutilisée.
3. GPT réellement lue identique à la référence 32Go incluse, secteurs de 512 octets.
4. En-tête seccfg V4 connu ; copie technique des premiers 512 octets conservée localement.
5. Une seule écriture de 512 octets, à l'adresse exacte de seccfg dans la zone user.
6. Relecture strictement identique ; erreur ou deuxième écriture refusée.
7. Redémarrage puis vérification indépendante de `product=dandelion` et `unlocked=yes`.

Les écritures de calibration, preloader et RPMB ne font pas partie du chemin
autorisé. Le flash Android est une commande distincte. Les journaux MTK bruts et
`seccfg.before.bin` restent **privés** dans le répertoire de travail ignoré par Git.
Les numéros USB peuvent différer selon les modes : si le contrôle indépendant ne
retrouve pas l'appareil sélectionné, il refuse de déclarer le déverrouillage validé.

Ce garde-fou n'identifie pas toutes les révisions matérielles existantes. Un modèle,
un SoC et une GPT identiques ne prouvent pas à eux seuls une compatibilité universelle.
En cas d'échec, lire le diagnostic privé et inspecter le téléphone avant de relancer.
