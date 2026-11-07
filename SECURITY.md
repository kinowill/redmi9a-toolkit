# Sécurité

Cet outil manipule potentiellement des partitions de démarrage. Il ne certifie
pas une ROM et ne rend pas un ancien appareil équivalent à un modèle maintenu.
L'ancienne base Xiaomi et les images custom peuvent conserver des vulnérabilités.

Le manifeste vient d'un opérateur de confiance. Une empreinte calculée depuis
une image malveillante reste l'empreinte d'une image malveillante. Les assertions
`audits` doivent correspondre à des vérifications du contenu, pas à des valeurs
copiées pour franchir un obstacle. Les binaires externes et le Python utilisés
doivent aussi être de confiance.

Le code garde ADB authentifié et SELinuxEnforcing, refuse des écritures hors
liste et arrête les opérations à la première erreur. Il ne répare pas tout seul
un flash partiel. Ne jamais supprimer ces contrôles pour obtenir un résultat vert.
Ne pas relocker le bootloader avec la GSI/boot personnalisés de référence.

Pour le téléphone : PIN robuste, autorisations minimales, root réservé aux
applications connues, applications/navigateur à jour et services exposés seulement
si nécessaires. Retirer le root réduit certains accès mais ne met pas à jour le
vendor ou le noyau. Une réinitialisation efface les données, pas les failles.

Ce dépôt ne réalise ni contournement de compte/FRP ni retrait d'une protection
Windows. L'accès USB normal, l'option OEM et les confirmations obligatoires
restent contrôlés par l'utilisateur et les systèmes concernés.

Pour signaler une faille de l'outil, utiliser le signalement privé GitHub s'il
est disponible. Sinon, ouvrir une issue sans secret ni détails d'exploitation
sensibles afin de convenir d'un canal privé avant leur transmission.
