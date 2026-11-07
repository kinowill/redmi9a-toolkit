# Journal de validation

## 2026-11-07 — reprise et état initial

Dossier cible vide, aucun dépôt Git initial. Dépôt neuf initialisé sur main.
Le chantier source est hors Git, sauf l'outil tiers MTKClient : modification
locale et données d'appareil présentes, non destinées à ce dépôt.

Téléphone réel lu par ADB : état device ; `su -c id` renvoie UID0 dans le domaine
Magisk. La validation d'origine couvre Lineage20/Android13, Magisk31.1,
Termux0.118.3 et redémarrage. Voir docs/VALIDATED_DEVICE.md pour limites.

Code local : initialisation et spécification. Publication : pas encore effectuée,
connexion GitHub CLI expirée ; nouvelle connexion demandée. Validation réelle du
nouvel outil : aucune à ce stade. Aucun flash ni effacement supplémentaire.

## 2026-11-07 — code et contrôles locaux

Code local : CLI diagnostic, inspection/extraction gzip, bundles, plan et
installation fastboot, adaptateur de déverrouillage MediaTek intégrés.
45 tests passent, y compris les hooks seccfg avec un faux DA : mauvaise GPT,
session réutilisée, deuxième écriture et mauvaise relecture sont refusées.
Ruff (analyse et format), mypy et Bandit niveau medium/high passent. Les quatre
alertes Bandit de faible niveau concernent subprocess, documenté sans suppression.
Construction wheel/sdist et installation éditable réussies.

Validation réelle : diagnostic et `verify --root-check` sur le téléphone actuel,
plan hors ligne sur les trois images de référence avec leurs SHA256/tailles.
La première lecture uname=armv8l a permis de corriger la détection du noyau par
lecture de sa configuration réelle, sans élargir aveuglément les valeurs acceptées.
État réel et preuves nettoyées dans docs/evidence et docs/VALIDATED_DEVICE.md.
Aucune nouvelle écriture de partition, aucun nouvel effacement, aucun relock.

Publication : connexion GitHub rétablie par le propriétaire ; préparation du
dépôt public en cours. Audit des 30 fichiers partageables sans secret ni chemin
personnel détecté. Diff d'écriture et contrôles relus avant publication.
Nettoyage de l'ancien chantier : désinstallations officielles en cours ; le
nouveau dépôt est explicitement conservé sur demande de l'utilisateur.
