# Lot de stabilité — version 16-preview

Branche : `codex/stability-review`. Ce lot est destiné à une application de prévisualisation ; `main` reste en version 15.

## Changements

- Réservations de quotas transactionnelles, verrou PostgreSQL partagé entre instances, compteurs utilisateur et plafond IA commun indépendants de la rotation d'identité.
- Limites par modèle appliquées au moment de la réservation ; nouvelles tentatives IA manuelles et comptées.
- Pool avec attente bornée, validation des connexions au retrait et remplacement des connexions invalides. Délais SQL et de verrou bornés.
- Éditeur : import et transformation préparés pour la prochaine exécution, puis appliqués avant la création du widget. Sauvegarde marquée réussie uniquement si la base confirme une ligne modifiée.
- PDF : limite de taille, de pages et de caractères, erreurs explicites, fermeture garantie, signature par contenu et préparation explicite de l'export. Les téléchargements d'un fichier déjà préparé ne réservent pas un nouveau quota.
- Aperçu Markdown sans HTML actif ni images distantes ; HTML fourni échappé dans les exports PDF.
- Exports Word sans duplication des éléments de liste. Sources web transmises au modèle et question courante non dupliquée.
- Chargement des 100 derniers messages, détails d'activité sans extraits de questions/cours. Les anciennes conversations ne sont pas supprimées par cette limitation d'affichage.
- Versions des dépendances et fichier de verrouillage ; CI Python 3.12 avec tests de widgets et tests JavaScript.

## Vérification réalisée

36 tests Python, dont trois parcours exécutés avec de vrais widgets Streamlit ; tests JavaScript de l'identité navigateur. Les exports PDF et Word sont générés et relus en mémoire avec leurs bibliothèques réelles. La base et l'IA des parcours Streamlit sont simulées. Les réservations concurrentes sont testées avec un double transactionnel, pas avec un serveur PostgreSQL réel.

## Avant fusion et déploiement

1. Créer une application Streamlit de test sur cette branche avec une base Neon de test. Installer `requirements.lock` avec Python 3.12. Les clés vont seulement dans les secrets de cette application.
2. Vérifier la connexion et le schéma via l'administration ; tester des réservations simultanées contre ce PostgreSQL de test, l'expiration et le nettoyage. Aucune connexion de production n'a été utilisée pour ce lot.
3. Vérifier deux profils de navigateur, rechargement et rotation d'identité ; import valide/invalide, deux PDF homonymes, conservation du texte après IA, exports Word et PDF.
4. Vérifier la présentation sur mobile et ordinateur. La maquette visuelle est indépendante et n'est pas encore intégrée à l'application.
5. Après validation, fusionner un commit ciblé, vérifier la CI, puis déployer. Retour possible à `ab1ec58` pour le code ; ce lot ne change pas le schéma des tables.

## Travaux suivants de l'audit

Le verrouillage administrateur au-delà de la session, les agrégations/pagination des statistiques, une politique de rétention et un déclenchement de nettoyage indépendants de la page d'accueil, la traduction des quotas en messages plus clairs et la nouvelle présentation restent à traiter séparément. Une identité anonyme par navigateur n'empêche pas à elle seule la création répétée d'espaces ; les plafonds globaux bornent les appels, mais ne constituent pas une protection complète contre le déni de service.
