# TalentRank AI

TalentRank AI est une application d'aide à l'analyse des candidatures. Elle permet de rassembler les CV d'une campagne et de retrouver, pour chaque critère d'une offre, les passages qui justifient une correspondance. Le recruteur peut ensuite comparer les dossiers et consigner son avis.

Le projet est développé avec GDG on Campus UCB pour la cinquième édition du Concours Africain de l'Innovation de l'UAT, en 2026.

Vous trouverez ici comment lancer l'application, comprendre son fonctionnement et essayer les modèles ML présents dans le code.

## Sommaire

- [Le projet et le concours](#le-projet-et-le-concours)
- [Lancement local avec Docker](#lancement-local-avec-docker)
- [Première utilisation](#première-utilisation)
- [Commandes courantes et mises à jour](#commandes-courantes-et-mises-à-jour)
- [Fonctionnalités et limites des résultats](#fonctionnalités-et-limites-des-résultats)
- [Architecture et dossiers](#architecture-et-dossiers)
- [Configuration](#configuration)
- [Options](#options)
- [Machine Learning et NLP](#machine-learning-et-nlp)
- [Développement et vérification](#développement-et-vérification)
- [Dépannage](#dépannage)
- [Préparation à la production](#préparation-à-la-production)
- [État du projet](#état-du-projet)

## Le projet et le concours

Lire un CV ne se résume pas à compter des mots-clés. Une compétence peut apparaître dans un projet, être citée dans une formation ou être présentée comme un objectif d'apprentissage. Ces situations demandent une lecture différente.

TalentRank AI cherche à faciliter ce travail. L'application extrait le texte des documents, repère les mentions de compétences et les relie aux critères de l'offre. Le recruteur peut revenir au passage concerné, vérifier le contexte et corriger une interprétation. Les points qui demandent un examen humain restent visibles.

Le volet ML sert à étudier comment retrouver les passages pertinents malgré les différences de vocabulaire. Le dépôt contient plusieurs approches, des méthodes lexicales aux modèles neuronaux locaux, avec leurs scripts d'évaluation. La décision de recrutement reste à la personne qui examine le dossier.

La note conceptuelle du concours met l'accent sur les solutions logicielles fondées sur l'IA et sur l'environnement académique qui accompagne leur développement. C'est dans ce cadre que s'inscrit le travail mené avec GDG on Campus UCB. Ce dépôt présente la solution et donne les moyens de l'examiner. Les informations sur l'équipe, le point focal et les justificatifs d'accompagnement institutionnel restent à joindre au dossier de candidature.

## Lancement local avec Docker

### Prérequis

Pour lancer le projet, il faut Docker avec Docker Compose, ainsi que Bash et OpenSSL pour créer la configuration locale. Démarrer le moteur Docker avant de commencer. Une connexion internet est nécessaire au premier lancement pour récupérer les images et les dépendances.

Les commandes ci-dessous se lancent depuis le dossier qui contient `docker-compose.yml`. Docker fournit Python 3.12 et Node 22.22.3 ; vous n'avez pas besoin de les installer sur votre machine pour ce parcours.

### Installation

```bash
# Créer la configuration locale avec des secrets aléatoires.
bash scripts/configure-dev.sh

# Démarrer les services de données.
docker compose up -d mysql redis minio

# Construire l'API, les workers et l'interface.
docker compose build api worker web

# Créer ou mettre à jour les tables, puis charger le référentiel de compétences.
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m scripts.seed_skills

# Démarrer l'application.
docker compose up -d api worker web
```

Ouvrir [la page de connexion](http://localhost:8080/connexion). Le port 8080 est publié uniquement sur l'interface locale `127.0.0.1`. Les autres services restent sur le réseau Docker.

Le script `configure-dev.sh` préserve les secrets d'un `.env` existant et peut ajouter certains paramètres manquants. Il ne remplace pas des valeurs indicatives déjà copiées depuis `.env.example`. Pour une installation neuve, laisser le script créer `.env` au lieu de copier l'exemple tel quel.

### Vérifier le démarrage

```bash
docker compose ps
curl --fail http://localhost:8080/health/live
curl --fail http://localhost:8080/health/ready
docker compose exec -T api alembic current
docker compose exec -T api python -m scripts.preflight --check-services
```

`/health/live` indique si l'API répond et `/health/ready` contrôle aussi sa connexion SQL. Le script `preflight` vérifie les autres services. Pour essayer le parcours complet, importez ensuite un CV fictif et attendez son traitement.

Le bucket MinIO privé est créé lors du premier dépôt de document. Avant ce premier import, le contrôle `storage-reachable` de `preflight` peut donc signaler un bucket absent.

## Première utilisation

### Créer une organisation

Sur la connexion, choisir « Créer un compte ». Le formulaire crée une organisation et son premier administrateur, puis ouvre le guide de démarrage. Conserver le code d'organisation : il sera demandé lors des connexions suivantes.

L'inscription administrateur ne demande pas de code OTP ni de confirmation email. Le mot de passe doit contenir entre 12 et 256 caractères. Pour rejoindre une organisation existante, utiliser une invitation de son administrateur.

Une création initiale en ligne de commande est également disponible :

```bash
docker compose exec -it api python -m scripts.bootstrap_admin \
  --organization "Organisation de test" \
  --slug organisation-test \
  --email admin@example.org \
  --name "Administrateur de test"
```

Remplacez les valeurs d'exemple par celles de votre organisation. Le mot de passe est demandé dans le terminal sans être affiché. Cette commande sert à créer une nouvelle organisation ; pour une organisation existante, utilisez la connexion habituelle.

### Effectuer un premier parcours

1. Créer une offre et sélectionner ses compétences dans le référentiel, puis confirmer les critères.
2. Créer une campagne liée à cette offre et l'activer.
3. Importer un PDF, un DOCX ou un ZIP de CV fictifs depuis les importations.
4. Attendre l'extraction et l'analyse NLP. Consulter les erreurs par fichier si le lot est incomplet.
5. Ouvrir les documents et examiner les mentions, les pages et les preuves détectées.
6. Lancer une analyse de matching sur la campagne, lire les explications et comparer les candidatures. Enregistrer les avis humains ou exporter un rapport selon les besoins.

Pour vos essais, des CV fictifs sont disponibles dans [datasets/synthetic](datasets/synthetic/). Les démonstrations et les exports peuvent produire des fichiers locaux dans `output/` et `exports/`. Ces dossiers sont exclus du suivi Git.

## Commandes courantes et mises à jour

Depuis la racine du projet :

```bash
# Relancer une installation déjà initialisée.
docker compose up -d

# Consulter les journaux récents.
docker compose logs --tail=100 api worker web

# Arrêter les conteneurs en conservant les volumes.
docker compose down
```

Les données MySQL, Redis et MinIO sont conservées dans des volumes Docker. Les profils facultatifs ajoutent leurs propres volumes. L'option `-v` de `docker compose down` efface les volumes : elle ne fait pas partie de l'arrêt normal.

Avant une mise à jour, sauvegarder `.env`, MySQL et les objets MinIO. Sauvegarder aussi Qdrant si la recherche sémantique est activée, puis vérifier la restauration dans un environnement séparé. Prévoir une interruption des imports et des traitements pendant la migration.

```bash
# Après sauvegarde, arrêter les services applicatifs standards.
docker compose stop web worker api

# Reconstruire, migrer et remettre à jour les compétences.
docker compose build api worker web
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m scripts.seed_skills

# Relancer et contrôler.
docker compose up -d api worker web
docker compose exec -T api python -m scripts.preflight --check-services
```

Si `vector-worker` est utilisé, l'arrêter aussi pendant la migration, puis relancer les services du profil `semantic`. Conserver les volumes et les secrets existants. Ne pas recréer l'administrateur lors d'une mise à jour.

## Fonctionnalités et limites des résultats

| Module | Fonction disponible |
| --- | --- |
| Comptes et équipe | Organisations distinctes, rôles, invitations et sessions révocables |
| Recrutement | Offres, critères confirmés, campagnes, candidats et candidatures |
| Documents | Import PDF/DOCX/ZIP, stockage privé, extraction, OCR français/anglais et suivi des lots |
| Compétences | Référentiel, synonymes et mentions contextualisées avec extraits et pages |
| Matching | Couverture documentaire, explications par critère, comparaison de 2 à 5 résultats et revue humaine |
| Évaluations | Affectation des dossiers et avis des évaluateurs affectés |
| Rapports | Tableau de bord, contrôles documentaires et exports CSV, XLSX ou PDF |
| Confidentialité | Rétention, conservation légale, prévisualisation et suppression contrôlée |
| Modules Africa | TalentGraph Africa, SkillsProof, ProofLab, FairRank et aperçu Opportunity Bridge |
| Options | Recherche sémantique locale, espace candidat avec consentement et accès de démonstration |

Le score décrit les critères retrouvés dans les documents. Il aide à comparer les dossiers, mais la maîtrise d'une compétence se vérifie avec le candidat.

Quand un critère est ambigu ou ne peut pas être évalué, l'application le signale pour examen. Un résultat incomplet peut avoir un score global `null` ; les critères évaluables sont alors présentés séparément. La présence d'un diplôme ou d'un certificat dans le texte ne vaut pas vérification de son authenticité.

Une modification des preuves peut rendre une analyse historique obsolète. Relancer l'analyse pour actualiser ses résultats. Les modèles du laboratoire ML ne sont pas automatiquement promus dans le calcul RH.

## Architecture et dossiers

```text
Navigateur Angular
    |
    v
Nginx :8080 -> FastAPI /api/v1 -> MySQL 8.4 / SQLAlchemy / Alembic
                  |
                  +-> MinIO : documents privés
                  |
                  +-> Redis -> Celery : extraction, OCR, NLP, matching
                                  |
                                  +-> Option : vector-worker
                                               -> service ML local -> Qdrant
```

L'accès aux données métier dépend de la session, du rôle et de l'organisation côté serveur. Qdrant sert d'index facultatif ; les résultats doivent aussi être autorisés par l'API et la base SQL.

| Chemin | Contenu |
| --- | --- |
| [apps/web](apps/web/) | Interface Angular, styles, tests unitaires, ressources et Nginx |
| [services/api/app](services/api/app/) | API FastAPI, authentification, métier, documents, NLP et workers |
| [services/api/app/ml](services/api/app/ml/) | Règles NLP, calcul documentaire, recherche sémantique et modèles expérimentaux |
| [services/api/alembic](services/api/alembic/) | Migrations SQL versionnées, jusqu'à `0015_demo_sessions` dans cette copie |
| [services/api/scripts](services/api/scripts/) | Initialisation, diagnostics et expériences de recherche |
| [services/api/tests](services/api/tests/) | Tests backend |
| [scripts](scripts/) | Configuration locale et contrôles frontend, navigateur et infrastructure |
| [datasets/synthetic](datasets/synthetic/) | Données fictives d'évaluation et corpus d'annotation |
| [docs/benchmarks](docs/benchmarks/) | Rapports JSON conservés, avec leur contexte synthétique ou expérimental |
| [docs/illustrations-v22.json](docs/illustrations-v22.json) | Inventaire des illustrations |
| `output/` | Résultats locaux de démonstration et fichiers générés, exclus du suivi Git |
| `exports/` | Exports locaux, exclus du suivi Git |
| [.github/workflows](.github/workflows/) | Vérifications automatisées backend, frontend et intégration manuelle |
| [docker-compose.yml](docker-compose.yml) | Services, profils, réseau et volumes |
| [.env.example](.env.example) | Noms et exemples indicatifs de configuration |

Le frontend est déclaré en version `0.28.0` dans `package.json`. L'API porte encore le numéro `0.27.0` dans `app/main.py`.

Les routes métier sont préfixées par `/api/v1`. La documentation OpenAPI de FastAPI existe sur `/docs` dans le conteneur API. Le Compose ne publie pas son port 8000, et le Nginx fourni ne transmet pas `/docs`. L'accès au Swagger nécessite la configuration de développement décrite plus bas.

## Configuration

La configuration privée est dans `.env`, ignoré par `.gitignore`. Ne jamais recopier ses valeurs dans le frontend, les rapports ou une capture partagée. Le script de création locale lui applique les permissions `600`.

| Variables | Usage |
| --- | --- |
| `ENVIRONMENT` | `development`, `test` ou `production` |
| `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` | Initialisation MySQL |
| `DATABASE_URL` | Connexion SQLAlchemy ; MySQL en exploitation et SQLite pour certains tests isolés |
| `JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE` | Signature et vérification des jetons |
| `CORS_ORIGINS`, `REFRESH_COOKIE_SECURE` | Origines autorisées et cookie sécurisé en HTTPS |
| `REDIS_URL` | File de traitement Celery |
| `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, `S3_SECURE` | Stockage MinIO privé et connexion TLS éventuelle |
| `OCR_LANGUAGES` | Langues OCR ; valeur locale `fra+eng` |
| `MALWARE_SCAN_ENABLED`, `CLAMAV_HOST`, `CLAMAV_PORT` | Analyse antivirus ; hôte interne par défaut `clamav:3310` |
| `SEMANTIC_ENABLED`, `EMBEDDING_MODEL`, `ML_SERVICE_URL`, `ML_SERVICE_TOKEN`, `QDRANT_URL` | Recherche sémantique facultative |
| `DEMO_ENABLED`, `DEMO_USER_EMAIL`, `DEMO_ORGANIZATION_SLUG`, `DEMO_ALLOW_WRITES` | Accès public à une organisation de démonstration dédiée |
| `CANDIDATE_PORTAL_ENABLED`, `CANDIDATE_PORTAL_SMTP_*`, `CANDIDATE_PORTAL_FROM_EMAIL`, `CANDIDATE_PORTAL_BASE_URL` | Espace candidat et envoi des liens de vérification |

Les paramètres complets et leurs contraintes sont définis dans [config.py](services/api/app/core/config.py). Par défaut, les limites applicatives sont de 60 000 000 octets par CV, 100 000 000 octets par ZIP, 3 000 documents par lot et 40 pages par PDF. Le Nginx applique aussi sa propre limite de requête ; modifier une limite côté API ne modifie pas celle du proxy.

Modifier les identifiants MySQL dans `.env` ne change pas les comptes d'une base déjà initialisée. Les identifiants de `DATABASE_URL` doivent correspondre à ceux réellement présents en base.

## Options

### Antivirus ClamAV

Le profil `security` ajoute ClamAV. Définir `MALWARE_SCAN_ENABLED=true` dans `.env`, puis :

```bash
docker compose --profile security up -d clamav
docker compose up -d --force-recreate api worker
docker compose exec -T api python -m scripts.preflight --check-services
```

Avant d'importer, vérifiez avec `preflight` que ClamAV répond et que ses signatures sont disponibles. Si `vector-worker` est actif, recréez aussi ce service après modification de sa configuration.

### Recherche sémantique locale

Définir `SEMANTIC_ENABLED=true` dans `.env` et conserver un `ML_SERVICE_TOKEN` privé valide, puis :

```bash
docker compose --profile semantic build ml-service vector-worker
docker compose --profile semantic up -d qdrant ml-service vector-worker api worker web
docker compose exec -T api python -m scripts.preflight --check-services
```

Le modèle configuré par défaut est `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Le premier chargement peut télécharger ses poids ; l'inférence s'exécute dans le service local. Les modèles sont conservés dans le volume `ml_models`. Prévoir les ressources nécessaires avant d'activer cette option. L'indexation passe par les tâches NLP et vectorielles ; les documents déjà présents peuvent nécessiter une réanalyse.

### Mode démonstration

Le bouton de démonstration de `/connexion` utilise une organisation et un administrateur existants, actifs et configurés côté serveur. Définir `DEMO_ENABLED=true`, `DEMO_USER_EMAIL` et `DEMO_ORGANIZATION_SLUG`, puis recréer l'API pour appliquer la configuration.

Conserver `DEMO_ALLOW_WRITES=false` pour une visite en consultation. Avec `true`, les visiteurs peuvent modifier les données de l'organisation de démo et ces changements sont partagés. Utiliser uniquement des données fictives dans cette organisation. Désactiver `DEMO_ENABLED` invalide les sessions de démonstration existantes.

### Espace candidat

L'espace candidat est désactivé par défaut. Son activation nécessite `CANDIDATE_PORTAL_ENABLED=true` et une configuration SMTP : `CANDIDATE_PORTAL_SMTP_HOST`, `CANDIDATE_PORTAL_SMTP_PORT`, `CANDIDATE_PORTAL_SMTP_USER`, `CANDIDATE_PORTAL_SMTP_PASSWORD`, ainsi que `CANDIDATE_PORTAL_FROM_EMAIL` et `CANDIDATE_PORTAL_BASE_URL`. Utiliser une URL HTTPS en production et vérifier réellement la livraison des messages.

Ce parcours de vérification par email concerne l'espace candidat. L'inscription du premier administrateur reste directe.

## Machine Learning et NLP

### Comment le traitement fonctionne

Le traitement commence par l'extraction du texte du CV. Les règles NLP repèrent ensuite les compétences et leur contexte. Le calcul documentaire utilise ces mentions pour expliquer les correspondances avec l'offre.

La recherche sémantique peut compléter cette lecture en retrouvant des passages proches par le sens. Elle s'active avec le profil `semantic`. Le laboratoire permet, lui, d'entraîner et de comparer plusieurs modèles hors ligne. Ces expériences restent séparées du calcul utilisé dans l'application. Leur code est regroupé dans [services/api/app/ml](services/api/app/ml/).

| Composant | Méthode et fonction | Sources principales |
| --- | --- | --- |
| Reconnaissance de compétences | spaCy avec `spacy.blank('xx')`, segmentation, lexique et synonymes ; aucune dépendance à des poids spaCy préentraînés | [recognition.py](services/api/app/ml/recognition.py), [terminology.py](services/api/app/ml/terminology.py) |
| Contexte et sections du CV | Règles français/anglais pour les négations, l'apprentissage, les exigences et les sections ; conservation des positions du texte source | [context.py](services/api/app/ml/context.py), [sections.py](services/api/app/ml/sections.py), [processing.py](services/api/app/ml/processing.py) |
| Couverture et classement documentaires | Calcul déterministe pondéré, résultats incomplets signalés et classement sur les mêmes critères évaluables pour les CV comparés | [matching.py](services/api/app/ml/matching.py), [matching_service.py](services/api/app/ml/matching_service.py), [documentary_ranking.py](services/api/app/ml/documentary_ranking.py) |
| Recherche lexicale et hybride | BM25, TF-IDF de caractères, similarité cosinus et fusion des rangs RRF ; recherche de passages avec embeddings et reclassement facultatifs | [retrieval_eval.py](services/api/app/ml/retrieval_eval.py), [hybrid_retrieval.py](services/api/app/ml/hybrid_retrieval.py), [hybrid_evaluation.py](services/api/app/ml/hybrid_evaluation.py) |
| Embeddings dans l'application | Sentence Transformers local, indexation des passages dans Qdrant et suggestions de libellés de compétences ; profil `semantic` requis | [vectors.py](services/api/app/ml/vectors.py), [skill_rank.py](services/api/app/ml/skill_rank.py), [sidecar.py](services/api/app/ml/sidecar.py) |
| Adaptateurs neuronaux de recherche | Encodeur Sentence Transformer et CrossEncoder chargés depuis des dossiers locaux explicitement fournis | [local_rerank.py](services/api/app/ml/local_rerank.py), [neural_eval_v24.py](services/api/app/ml/neural_eval_v24.py) |
| Classification binaire | TF-IDF de caractères et régression logistique ; expérience sur des paires critère/preuve annotées `0` ou `1` | [supervised.py](services/api/app/ml/supervised.py) |
| Classification à trois classes | TF-IDF de mots et caractères, régression logistique, classes `supports`, `related`, `insufficient` et abstention calibrée | [pair_classifier.py](services/api/app/ml/pair_classifier.py) |
| Classement appris par paires, v11 | Régression logistique sur des préférences annotées entre passages ; sélection sur calibration et comparaison aux références lexicales | [pairwise_ranker.py](services/api/app/ml/pairwise_ranker.py), [ranking_experiment.py](services/api/app/ml/ranking_experiment.py) |
| Apprentissage contrastif, v12 | PyTorch entraîne une projection de caractéristiques textuelles hachées de dimension 512 vers 48 ; aucun modèle préentraîné nécessaire | [contrastive_v12.py](services/api/app/ml/contrastive_v12.py) |
| Fine-tuning neuronal, v13 | Ajustement d'un Sentence Transformer préentraîné local sur des triplets critère, passage pertinent et passage trompeur ; CPU, MPS ou CUDA selon disponibilité | [neural_finetune_v13.py](services/api/app/ml/neural_finetune_v13.py) |
| Calibration et contrôles | Sélection de seuils sur annotations, abstention, intervalles de Wilson, contrôles des variations de texte et audit de recherche | [calibration.py](services/api/app/ml/calibration.py), [confidence_gate.py](services/api/app/ml/confidence_gate.py), [robustness.py](services/api/app/ml/robustness.py), [release_audit_v14.py](services/api/app/ml/release_audit_v14.py) |
| ProofLab et FairRank | Évaluations de recherche documentaire, essais d'invariance à des identités fictives et audits par groupes fournis | [africa_evaluation.py](services/api/app/ml/africa_evaluation.py), [fairrank.py](services/api/app/ml/fairrank.py), [fairness_lab_v24.py](services/api/app/ml/fairness_lab_v24.py) |
| Annotation | Validation des paires et de leur provenance, double annotation et préparation de passages à faire examiner | [annotation.py](services/api/app/ml/annotation.py), [active_review_v14.py](services/api/app/ml/active_review_v14.py) |

Le classement documentaire repose sur une formule pondérée. Les modèles supervisés apprennent à partir de paires ou de passages annotés, plutôt qu'à partir des anciennes décisions de recrutement. Les résultats de recherche vectorielle restent des passages à examiner.

### Dépendances ML

Choisissez les dépendances selon l'expérience que vous voulez lancer. Une ligne `-r` reprend le contenu d'un autre fichier.

| Fichier dans `services/api` | Contenu et usage |
| --- | --- |
| [requirements.txt](services/api/requirements.txt) | API, spaCy et traitement documentaire standard |
| [requirements-ml-lab.txt](services/api/requirements-ml-lab.txt) | scikit-learn pour les expériences CPU de classification et de recherche |
| [requirements-ml-v10.txt](services/api/requirements-ml-v10.txt) et [requirements-ml-v11.txt](services/api/requirements-ml-v11.txt) | Recherche hybride puis classement par paires ; v11 ajoute pytest |
| [requirements-ml-v12.txt](services/api/requirements-ml-v12.txt) | Dépendances précédentes, NumPy et PyTorch pour la projection contrastive |
| [requirements-ml-v13.txt](services/api/requirements-ml-v13.txt) | Dépendances v12 et Sentence Transformers pour le fine-tuning local |
| [requirements-ml.txt](services/api/requirements-ml.txt) | API et Sentence Transformers ; utilisé par `Dockerfile.ml` pour le service sémantique |
| [requirements-training.txt](services/api/requirements-training.txt) | API et scikit-learn pour les premières expériences supervisées |
| [requirements-test.txt](services/api/requirements-test.txt) | Dépendances de développement API et laboratoire jusqu'à v12 pour les tests |

Pour la recherche sémantique dans l'application, suivre [l'activation du profil Docker](#recherche-sémantique-locale). Les commandes suivantes concernent le laboratoire sur l'hôte et se lancent depuis `services/api`, sans modifier les données de l'application.

### Lancer les expériences synthétiques

Depuis la racine, préparer un environnement Python 3.12. Réutiliser `.venv` s'il a déjà été créé pour les tests backend.

```bash
cd services/api
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
mkdir -p ../../output/ml-local
```

Les exemples écrivent leurs rapports dans `output/ml-local` pour conserver les rapports historiques de `docs/benchmarks`. Relancer une commande avec le même chemin de sortie remplace son rapport précédent.

Évaluer les règles NLP, la recherche TF-IDF et le tri à trois classes sur les jeux fournis :

```bash
python -m scripts.evaluate_nlp \
  --dataset ../../datasets/synthetic/nlp-context-evaluation.jsonl
python -m scripts.evaluate_retrieval \
  ../../datasets/synthetic/evidence-retrieval-benchmark.json
python -m scripts.train_evidence_triage \
  ../../datasets/synthetic/evidence-triage-annotations.jsonl \
  --output ../../output/ml-local/classification-trois-classes.json
```

Comparer BM25, TF-IDF et leur fusion RRF, puis entraîner et évaluer le modèle de classement par paires :

```bash
python -m scripts.benchmark_hybrid_v10 \
  ../../datasets/synthetic/hybrid-retrieval-v10.json \
  --output ../../output/ml-local/recherche-hybride.json
python -m scripts.learn_to_rank_v11 \
  ../../datasets/synthetic/hybrid-retrieval-v10.json \
  --manifest ../../datasets/synthetic/ranking-families-v11.json \
  --output ../../output/ml-local/classement-paires-rapport.json \
  --artifact ../../output/ml-local/classement-paires-modele.json
python -m scripts.evaluate_challenges_v11 \
  ../../datasets/synthetic/ranking-challenges-v11.json \
  --artifact ../../output/ml-local/classement-paires-modele.json \
  --output ../../output/ml-local/classement-paires-cas-pieges.json
```

Entraîner la projection contrastive v12 et préparer les triplets de fine-tuning v13 sans charger de modèle préentraîné :

```bash
python -m scripts.train_contrastive_v12 \
  ../../datasets/synthetic/hybrid-retrieval-v10.json \
  --manifest ../../datasets/synthetic/ranking-families-v11.json \
  --output ../../output/ml-local/contrastif-rapport.json \
  --artifact ../../output/ml-local/contrastif-projection.json
python -m scripts.finetune_multilingual_v13 \
  ../../datasets/synthetic/hybrid-retrieval-v10.json \
  --manifest ../../datasets/synthetic/ranking-families-v11.json \
  --dry-run --output ../../output/ml-local/preparation-fine-tuning.json
```

Avec `--dry-run`, vous vérifiez la préparation des données avant de charger un Sentence Transformer. La projection v12, de son côté, apprend ses propres poids sur des caractéristiques hachées ; les poids de MiniLM restent inchangés.

### Utiliser un modèle neuronal local

Installer le complément v13 dans le même environnement. Les chemins `/chemin/prive/...` ci-dessous sont des emplacements à remplacer : le dossier du modèle doit déjà contenir ses poids et sa configuration.

```bash
python -m pip install -r requirements-ml-v13.txt
python -m scripts.model_preflight_v25 \
  --local-model /chemin/prive/modele-local \
  --report ../../output/ml-local/disponibilite-modele.json
python -m scripts.finetune_multilingual_v13 \
  ../../datasets/synthetic/hybrid-retrieval-v10.json \
  --manifest ../../datasets/synthetic/ranking-families-v11.json \
  --local-model /chemin/prive/modele-local \
  --device cpu --epochs 3 --batch-size 4 \
  --checkpoint /chemin/prive/checkpoints/experience-v13 \
  --output ../../output/ml-local/fine-tuning-rapport.json
```

Cet exemple utilise les annotations synthétiques fournies pour un essai technique. Pour mesurer la qualité sur des données réelles, préparer un corpus autorisé avec des annotations indépendantes, puis :

```bash
python -m scripts.neural_benchmark_v24 \
  --corpus /chemin/prive/corpus-annote.json \
  --local-encoder /chemin/prive/modele-local \
  --device cpu --output /chemin/prive/rapport-recherche.json
```

`neural_benchmark_v24` accepte aussi `--local-reranker` pour un CrossEncoder. `benchmark_hybrid_v10` accepte `--embedding-dir` et `--crossencoder-dir` pour comparer ces méthodes sur son format de corpus ; le CrossEncoder y nécessite aussi l'encodeur. Ces commandes de laboratoire chargent explicitement des modèles locaux. Le service sémantique Docker peut, lui, télécharger le modèle configuré au premier chargement.

Conserver les checkpoints dans un emplacement privé : les poids entraînés peuvent retenir des informations des textes d'entraînement. Les scripts ne déploient pas ces poids et ne changent pas le calcul de matching.

### Jeux de données, annotation et audits

| Données fournies | Usage |
| --- | --- |
| [nlp-evaluation.jsonl](datasets/synthetic/nlp-evaluation.jsonl), [nlp-context-evaluation.jsonl](datasets/synthetic/nlp-context-evaluation.jsonl) | Cas de régression lexicale et contextuelle français/anglais |
| [evidence-triage-annotations.jsonl](datasets/synthetic/evidence-triage-annotations.jsonl) | Paires critère/preuve avec classes et annotations fictives |
| [evidence-retrieval-benchmark.json](datasets/synthetic/evidence-retrieval-benchmark.json) | Évaluation de recherche de passages |
| [hybrid-retrieval-v10.json](datasets/synthetic/hybrid-retrieval-v10.json), [ranking-families-v11.json](datasets/synthetic/ranking-families-v11.json) | Passages, requêtes, jugements et séparation des familles pour les expériences v10 à v14 |
| [ranking-challenges-v11.json](datasets/synthetic/ranking-challenges-v11.json) | Cas pièges pour le classement par paires |
| [science-evaluation-v24-SYNTHETIC.json](datasets/synthetic/science-evaluation-v24-SYNTHETIC.json) | Corpus scientifique synthétique, sans validation RH réelle |
| [fairness-pairs-v24-SYNTHETIC.json](datasets/synthetic/fairness-pairs-v24-SYNTHETIC.json), [fairness-aliases-v24-SYNTHETIC.json](datasets/synthetic/fairness-aliases-v24-SYNTHETIC.json) | Variations contrôlées pour les essais FairRank |
| [v25-review-corpus](datasets/synthetic/v25-review-corpus/) | CV synthétiques et grilles CSV d'annotation vierges pour deux évaluateurs |

Les grilles `BLANK` sont vierges : elles sont prévues pour deux évaluateurs. Les attendus techniques fournis servent aux essais et restent distincts de leurs annotations.

Les scripts complémentaires suivants se lancent avec `python -m scripts.NOM --help` depuis `services/api` :

| Script | Entrée ou fonction |
| --- | --- |
| `train_pair_classifier` | CSV binaire à fournir : colonnes `group,split,requirement,evidence,equivalent,language`, avec `equivalent` à `0` ou `1` et `split` à `train` ou `validation` |
| `calibrate_semantic` | CSV à fournir : `group,split,score,equivalent,language` ; sélection d'un seuil sur des scores d'un modèle fixé |
| `active_review_v14` | Prépare une file privée non annotée, limitée à l'organisation demandée et au sous-ensemble d'entraînement |
| `audit_release_v14` | Compare les résultats aux références lexicales et vérifie les conditions de recherche ; `--strict` retourne un échec si les conditions ne sont pas réunies |
| `prooflab_v23` | Évaluation synthétique reproductible des passages |
| `fairness_lab_v24` | Variations contrôlées avec `--pairs` et `--aliases`, ou audit de groupes fournis avec `--groups` |
| `validate_dual_review_v25` | Compare deux CSV remplis, mesure les accords et les désaccords ; ne certifie pas l'identité des évaluateurs |

Selon le module, les rapports donnent la précision, le rappel, le F1 ou le rang des passages pertinents, avec des mesures comme MRR, Hit@k et Recall@k. Pour comprendre un résultat, regardez aussi les faux positifs, les abstentions et les écarts entre langues. Les données d'entraînement, de calibration et de test sont contrôlées pour limiter les recoupements ; une évaluation sur de nouveaux candidats reste nécessaire.

Les règles lexicales couvrent le français et l'anglais. Le swahili reste expérimental et désactivé pour le matching. Les essais fournis portent sur des données synthétiques. Pour évaluer les modèles sur des CV réels, il reste à réunir un corpus autorisé, des annotations humaines indépendantes et les poids des modèles concernés.

## Développement et vérification

### Interface Angular

Pour travailler hors du conteneur, utiliser une version Node autorisée par [package.json](apps/web/package.json) : `^22.22.3`, `^24.15.0` ou `>=26.0.0`. Le lockfile npm est fourni.

```bash
cd apps/web
npm ci
npm run test:static
npm run test:unit
npm run build
```

Lancer chaque contrôle séparément pour examiner ses résultats si un précédent échoue. Les contrôles statiques sont des assertions sur les sources ; ils ne remplacent pas les tests unitaires ni le navigateur.

`npm start` ouvre le serveur Angular sur le port 4200. Son fichier `proxy.conf.json` attend une API sur `localhost:8000`, alors que le Compose standard ne publie pas ce port. Pour conserver le backend Docker, créer un fichier local `compose.dev.yml` à la racine avec :

```yaml
services:
  api:
    ports:
      - "127.0.0.1:8000:8000"
```

Puis, depuis la racine :

```bash
docker compose -f docker-compose.yml -f compose.dev.yml up -d api
```

Et depuis `apps/web` :

```bash
npm start
```

Ouvrir [l'interface de développement](http://localhost:4200/connexion). Cette publication locale du port donne aussi accès au [Swagger de développement](http://localhost:8000/docs). Garder cette surcharge pour le développement local.

### Backend et migrations

Pour un environnement Python sur l'hôte, utiliser Python 3.12, version de l'image API. Certains tests de recherche nécessitent scikit-learn ou PyTorch en plus des dépendances API.

```bash
cd services/api
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m pytest -q
```

Les tests utilisent une base SQLite temporaire, préparée par `tests/conftest.py`. Les essais d'intégration et de charge doivent aussi être exécutés sur MySQL. Pour les expériences neuronales, `requirements-ml-v13.txt` ajoute Sentence Transformers ; les poids du modèle sont à fournir séparément.

Pour vérifier le schéma de l'installation Docker existante :

```bash
docker compose exec -T api alembic current
docker compose exec -T api alembic check
```

Ces deux commandes se lancent depuis la racine du projet.

### Vérification intégrée

Avec l'application déjà démarrée et Python disponible sur l'hôte :

```bash
python3 scripts/verify_release_v28.py \
  --output docs/benchmarks/verification-locale.json
```

Ce script contrôle les conteneurs et les services depuis l'API. Il donne un premier diagnostic de l'installation.

Pour les essais qui créent des enregistrements, préparer une organisation exclusivement fictive et définir dans un terminal privé `TR_SMOKE_URL`, `TR_SMOKE_ORG`, `TR_SMOKE_EMAIL` et `TR_SMOKE_PASSWORD`. Installer `httpx`, `python-docx` et `playwright` dans un environnement Python de test, puis :

```bash
python3 scripts/verify_release_v28.py --smoke \
  --output docs/benchmarks/verification-parcours-fictif.json
python3 -m playwright install chromium
python3 scripts/browser_smoke_v28.py
```

Le scénario navigateur fourni vérifie la connexion et le débordement horizontal à 1366 et 390 px. Compléter par un contrôle à 375 px, au clavier, avec les états de chargement et d'erreur. Il ne couvre pas à lui seul tous les écrans métier.

Le workflow `release-integration.yml` se déclenche manuellement dans GitHub Actions. Les workflows backend et frontend s'exécutent sur les changements de leurs chemins configurés. Le backend utilise `requirements-test.txt`, qui regroupe les dépendances API et celles du laboratoire ML hors ligne.

### Mesures de performances

Les expériences d'apprentissage sont détaillées dans [Machine Learning et NLP](#machine-learning-et-nlp). Les mesures de débit utilisent les scripts suivants depuis `services/api` ; leur option `--help` décrit les paramètres.

| Script | Objet de la mesure |
| --- | --- |
| `benchmark_matching` | Calcul déterministe seul sur des cas synthétiques |
| `benchmark_offline_documents_v25` | Génération et analyse locale de DOCX synthétiques |
| `benchmark_3000_v24` | Import HTTP, traitement et matching contre une installation active ; crée des données fictives persistantes |

Les rapports de `docs/benchmarks` permettent de retrouver les essais précédents et leurs conditions. Pour mesurer le débit de l'application, utilisez le parcours HTTP complet : un temps d'analyse DOCX hors ligne ne couvre pas le stockage, les files d'attente et les autres traitements.

## Dépannage

| Symptôme | Vérification |
| --- | --- |
| Docker ne répond pas | Démarrer Docker Desktop ou le moteur Docker, puis exécuter `docker compose ps` |
| Le port 8080 est occupé | Libérer ce port ou adapter sa publication et les origines autorisées |
| L'API ne démarre pas | Consulter ses journaux, l'état MySQL, la configuration et les migrations |
| Une table ou une colonne manque | Exécuter `docker compose run --rm api alembic upgrade head` après sauvegarde |
| Un lot reste en attente | Vérifier `worker`, Redis et les journaux Celery ; une API disponible ne prouve pas que les tâches s'exécutent |
| L'OCR échoue | Vérifier la lisibilité du document et les langues Tesseract installées dans le worker |
| Un fichier est refusé | Consulter l'erreur du lot, le format, la taille et, si activé, ClamAV |
| La recherche sémantique ne répond pas | Vérifier le profil `semantic`, le chargement du modèle, les workers et le jeton interne |
| Angular sur 4200 ne joint pas l'API | Vérifier le proxy vers 8000 et la surcharge Docker de développement |
| La connexion répond 429 | Attendre la fin de la limitation des tentatives Nginx |
| Le bouton démo ne fonctionne pas | Vérifier son activation côté serveur, l'organisation, l'administrateur actif et les migrations |

Ne pas partager les valeurs de `.env` ni des journaux contenant des données candidates pour demander de l'aide.

## Préparation à la production

Le Compose fourni sert au lancement local. Un déploiement exposé nécessite un domaine réel, un reverse proxy HTTPS et des paramètres adaptés à l'exploitant. La configuration de production exige notamment MySQL, des origines CORS HTTPS explicites, un cookie Secure et l'antivirus activé.

Avant un usage avec des CV personnels, vérifier l'authentification, les rôles et l'isolation par organisation sur les opérations et les identifiants demandés. Conserver Argon2 et les cookies HttpOnly, SameSite et Secure en production. Garder les secrets côté serveur et les services de données sur un réseau privé.

Vérifier les dépendances, les images, les en-têtes de sécurité et le comportement du proxy public. Le Nginx fourni interdit l'indexation et pose une politique CSP. Une terminaison HTTPS externe doit aussi préserver la sécurité des cookies et la limitation des tentatives avec des adresses client fiables. Contrôler les métadonnées, les ressources de partage, le favicon, les liens, les textes alternatifs, la page 404 et l'affichage à 375 px avant de déclarer l'interface prête.

Les sauvegardes, exports déjà téléchargés et copies externes nécessitent leur propre politique de conservation. La suppression dans MySQL, MinIO et Qdrant n'est pas une transaction distribuée atomique : tester les pannes et la réconciliation. La suppression d'un dossier dans l'application ne prouve pas l'effacement de toutes ses copies.

Pour une installation réelle, le responsable du service devra renseigner le domaine, ses coordonnées et les durées de conservation, ainsi que le SMTP si l'espace candidat est activé. Il reste aussi à tester la restauration des sauvegardes et les performances sur l'environnement cible, puis à mener l'audit de sécurité et l'évaluation des modèles sur des données autorisées.

## État du projet

Le dépôt contient l'application, les scripts de traitement et le laboratoire ML. Il permet de préparer une démonstration locale avec des données fictives. Un déploiement destiné à de vrais candidats demande encore les validations décrites plus haut.

Au contrôle du 31 octobre 2026, la configuration Compose est valide et les vérifications frontend v15, v16, v19 et v24 passent. Quatre autres vérifications échouent sur les attentes suivantes :

| Contrôle | Échec observé |
| --- | --- |
| v17 | Attend le texte « Paramètres réservés aux administrateurs » dans la page de matching |
| v20 | Exige une icône Lucide dans `applications.spec.ts`, qui est un fichier de test |
| v21 | Attend l'expression `scope(r)` dans le comparateur |
| v26 | Attend l'ancien libellé de navigation « Mon accueil » |

Ces points restent à corriger pour que `npm run test:static` passe entièrement. Les rapports de recherche déjà présents doivent être lus avec leur jeu de données et leur configuration. La disponibilité des scripts d'entraînement ne signifie pas qu'un modèle neuronal a été entraîné et validé pour le recrutement.
