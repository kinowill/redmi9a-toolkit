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

## 2026-11-07 — publication et CI

Dépôt public créé et code poussé sur main :
https://github.com/kinowill/redmi9a-toolkit.
CI de la publication initiale 0ca25fc réussie sur Windows/Linux/macOS et Python3.10/3.13,
soit six configurations. Les 45 tests et analyses locales passent.

Correction de confidentialité additionnelle : tout répertoire choisi pour une
session MTK reçoit son propre fichier d'exclusion Git avant les données privées,
même si l'opérateur ne choisit pas le répertoire work recommandé. Ruff/mypy et
45 tests repassés ; diff relu avant publication de cette petite correction.

Téléphone : état actuel conservé, root confirmé, nouvelles écritures de partition
non exécutées. PC : les quatre uninstallateurs ont terminé avec code0, aucun
redémarrage demandé, paquets absents du registre et service usbipd absent.
Suppression des anciens fichiers après mise à jour de la trace sur téléphone
encore en cours ; le dépôt communautaire est conservé.

## 2026-11-07 — nettoyage vérifié et limite de suppression

Code local et distant : première version publiée, correction de confidentialité
poussée. Diagnostic réel et root recontrôlés avec l'ADB préexistant après retrait
des logiciels temporaires. Téléphone inchangé ; aucune nouvelle écriture de partition.

WSL/Ubuntu du chantier, ancien kernelWSL, usbipd et UsbDk retirés via les
uninstallateurs officiels. Aucun redémarrage demandé. ADB préexistant et logiciels
sans lien avec le chantier conservés, aucun journal global Windows effacé.

Le contrôle automatique a refusé la suppression définitive du dossier historique,
sans motif détaillé au-delà de « blocked by policy ». L'alternative réversible
vers la corbeille Windows a réussi : ancien dossier, ancien maître et lanceur
absents du Bureau. Les fichiers restent récupérables dans la corbeille ; une
purge définitive et une absence absolue de traces PC ne sont pas revendiquées.
La trace nettoyée et le compte rendu ont été copiés sur le téléphone avant retrait,
avec quatre SHA256 comparés. Le nouveau dépôt demandé reste présent.

## 2026-11-07 — état final des livrables

Correction de confidentialité b43dcf9 passée dans les six configurations CI.
Code local publié sur main, documentation de validation et limites alignées.
Téléphone réel : root toujours UID0 après retrait des pilotes temporaires et
retour à l'ADB préexistant. Aucun flash supplémentaire exécuté.

Cinq rapports finaux dans Documents/Redmi9A sur le téléphone, NETTOYAGE_PC.txt
inclus, empreintes SHA256 comparées. Le premier contrôle d'une mise à jour via
stdin ADB n'était pas concordant ; la cause exacte n'a pas été établie. Le
transfert binaire via push a ensuite produit cinq empreintes identiques.
Une vérification intermédiaire en échec n'a pas été comptée comme un succès.

Reste explicitement non réalisé : purge définitive des anciens fichiers
(refus du contrôle automatique), essai matériel complet des nouveaux unlock/install,
portages/autres profils et préparation automatique des images. La première
version partageable est livrée ; aucune compatibilité universelle n'est annoncée.

Archive du code public à la révision3012a2a, README et journal communautaire
copiés également sur le téléphone et vérifiés par SHA256 : huit fichiers vérifiés
au total. Les copies de transfert intermédiaires ont été retirées du répertoire
de travail ; les anciens originaux restent récupérables dans la corbeille.
