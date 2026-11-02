# Lot de stabilité — version 16-review

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

45 tests Python, dont six parcours exécutés avec de vrais widgets Streamlit ; tests JavaScript de l'identité navigateur. Les exports PDF et Word sont générés et relus en mémoire avec leurs bibliothèques réelles. La base et l'IA des parcours Streamlit sont simulées. Les réservations concurrentes sont testées avec un double transactionnel, pas avec un serveur PostgreSQL réel.

## Avant fusion et déploiement

1. Créer une application Streamlit de test sur cette branche avec une base Neon de test. Installer `requirements.lock` avec Python 3.12. Les clés vont seulement dans les secrets de cette application.
2. Vérifier la connexion et le schéma via l'administration ; tester des réservations simultanées contre ce PostgreSQL de test, l'expiration et le nettoyage. Aucune connexion de production n'a été utilisée pour ce lot.
3. Vérifier deux profils de navigateur, rechargement et rotation d'identité ; import valide/invalide, deux PDF homonymes, conservation du texte après IA, exports Word et PDF.
4. Vérifier la présentation sur mobile et ordinateur. Le design validé est intégré ; vérifier les vues Écrire/Aperçu et le mode sombre.
5. Après validation, fusionner un commit ciblé, vérifier la CI, puis déployer. Retour possible à `ab1ec58` pour le code ; la colonne additionnelle `sessions.draft_title` peut rester en place sans empêcher l'ancienne version de fonctionner.

## Dernier lot intégré

- Navigation déclarée explicitement avec conservation des URL `/Chat`, `/Editeur`, `/Feedback` et `/admin_secret_access` ; accueil déplacé dans `pages/0_Accueil.py`.
- Présentation sobre du chat et de l'éditeur, modèle visible, cours repliable, quotas secondaires repliés, vues Écrire/Aperçu.
- Effacement explicitement nommé et confirmé, état local conservé lorsque la suppression en base échoue.
- Nettoyage transactionnel avec verrou entre instances, date de réussite écrite dans la même transaction, vérification depuis toutes les pages. Tant que l'application est inactive, elle ne peut pas exécuter de tâche ; `python scripts/cleanup.py` est fourni pour un planificateur externe si une suppression à heure fixe est nécessaire.
- Connexion administrateur limitée à 30 minutes et compteur d'échecs partagé en base (5 échecs, verrouillage de cinq minutes). Le compte administrateur étant unique, un verrouillage concerne tous ses navigateurs. Aucun mot de passe n'est conservé dans ce compteur.
- Totaux statistiques calculés en SQL sur toute la période demandée ; listes de détails limitées à 100 lignes ; statistiques partielles signalées.
- Titre du brouillon sauvegardé. La première ouverture de l'éditeur exécute l'ajout idempotent de la colonne `sessions.draft_title` si elle manque. Cela exige le droit ALTER sur `sessions` ; la commande est aussi fournie dans `neon_migration.sql`. Les textes existants ne sont pas réécrits. Ne pas confondre cette initialisation avec le contrôle de connexion, qui reste en lecture seule.

## Limites de validation

La base et l'IA des tests restent simulées. Aucune modification n'a été exécutée sur la base Cloud. La connexion réelle, les verrous PostgreSQL en concurrence et l'apparence sur plusieurs appareils doivent être validés sur une application de test. L'outil de navigateur local n'a pas pu s'initialiser ; les parcours de widgets sont vérifiés avec Streamlit AppTest, pas avec des captures de navigateur.

Une identité anonyme par navigateur n'empêche pas la création répétée d'espaces ; les plafonds globaux bornent les appels, mais ne constituent pas une protection complète contre le déni de service. Le rôle de base de données de l'application doit rester confidentiel et les anciennes clés publiées doivent être révoquées.
