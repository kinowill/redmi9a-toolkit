# État de validation — 7 novembre 2026

## Procédure d'origine : téléphone réel

Une unité Redmi9A M2006C3LG/dandelion 2Go/32Go, vendor MIUI EEA
V12.0.17.0.QCDEUXM, noyau stock4.9.190. Déverrouillage MediaTek confirmé par
écriture/relecture seccfg512octets, puis Android locked0 et fastboot unlockedyes.

LineageOS20 `20.0-20251021-UNOFFICIAL-a64_bvN`, Android13, démarre après
installation et redémarrage. Root Magisk31.1 confirmé UID0 pour Shell et
Termux0.118.3 après redémarrage. ADB authentifié, confiance USB normale
persistante, SELinuxEnforcing, chiffrement `encrypted` / `file`.

Wi-Fi/Bluetooth activables et interfaces présentes, deux caméras détectées.
La caméra arrière a produit 446images de prévisualisation ; aucune photo
personnelle n'a été prise pour le rapport. VeilleDozing puis réveilAwake
observés. Les réglages choisis par l'utilisateur ont été conservés.

Limites : pas deSIM pour appels/données mobiles ; pas de validation à l'écoute
du son/micro, pas de test GPS extérieur ni d'appairage Bluetooth, pas de capture
JPEG ni de vérification effective de la caméra frontale. Aucun benchmark
comparatif contrôlé ne prouve un gain de RAM ou de vitesse par rapport à MIUI.
La restauration stock reste non testée sur appareil.

Correctif système lu : **2025-09-05**. Correctif vendor lu : **2020-03-05**.
Un Android plus récent et un chiffrement actif ne corrigent pas magiquement les
anciens composants propriétaires, le modem ou le noyau Xiaomi conservé.

## Nouveau programme : validations distinctes

`doctor` et `verify --root-check` ont été exécutés réellement en lecture seule
sur ce téléphone. Ils retrouvent le profil, les trois options noyau ARM64/binder64,
le démarrage complet, le root, l'authentification ADB et SELinuxEnforcing.

Le premier diagnostic ne reconnaissait que `uname=aarch64` ; la lecture réelle
renvoie `armv8l` dans le contexte32bits. La cause a été vérifiée dans la configuration
noyau et la compatibilité ARM64 Linux. Le contrôle a été remplacé par la lecture
explicite de CONFIG_ARM64, CONFIG_64BIT et CONFIG_ANDROID_BINDER_IPC_32BIT.

Les parcours `install` et `unlock` utilisent des transports simulés dans les tests :
refus des mauvaises identités, partitions et tailles, un seul seccfg512octets,
relecture défaillante, pas de nouvelle tentative et pas d'effacement après échec.
**Aucune exécution matérielle des nouvelles commandes d'écriture.** Leur réussite
sur de futurs appareils devra être documentée séparément, avec leur révision.

Les tests logiciels et la CI ne valident pas le support des pilotes ni les
fonctions téléphoniques. Aucune image binaire ni donnée d'appareil n'est publiée.
