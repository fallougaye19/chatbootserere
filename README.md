# Application de Traduction Sérère

Une application web full-stack pour la traduction bidirectionnelle entre le français et le sérère, avec une interface de type chat et une architecture prête pour l'intégration d'API de modèles IA NLP externes.

## 🏗️ Architecture

- **Frontend**: React + TypeScript + Tailwind CSS
- **Backend**: FastAPI + Python
- **Base de données**: PostgreSQL + SQLAlchemy
- **Authentification**: JWT (JSON Web Tokens)
- **Sécurité**: Hachage des mots de passe avec bcrypt

## 🚀 Installation et Démarrage

### Prérequis

- Python 3.8+
- Node.js 16+
- PostgreSQL 12+

### Backend

1. **Installation des dépendances**:
```bash
cd backend
pip install -r requirements.txt
```

2. **Configuration de la base de données**:
```bash
# Créer la base de données PostgreSQL
createdb serere_translation

# Copier le fichier de configuration
cp env.example .env
# Éditer .env avec vos paramètres de base de données
```

3. **Démarrage du serveur**:
```bash
python main.py
```

Le serveur sera accessible sur `http://localhost:8000`

### Frontend

1. **Installation des dépendances**:
```bash
cd frontend
npm install
```

2. **Démarrage du serveur de développement**:
```bash
npm start
```

L'application sera accessible sur `http://localhost:3000`

## 🔧 Configuration

### Variables d'environnement (Backend)

Créez un fichier `.env` dans le dossier `backend` avec :

```env
DATABASE_URL=postgresql://username:password@localhost:5432/serere_translation
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
AI_MODEL_URL=https://your-ai-model-api.com
```

## 📡 API Endpoints

### Authentification
- `POST /api/v1/auth/register` - Inscription
- `POST /api/v1/auth/login` - Connexion
- `GET /api/v1/auth/me` - Informations utilisateur

### Traduction (Protégés par JWT)
- `POST /api/v1/ia/translate_audio/` - Audio → Texte
- `POST /api/v1/ia/synthesize_text/` - Texte → Audio
- `GET /api/v1/history` - Historique des traductions

## 🎯 Fonctionnalités

### Interface Utilisateur
- **Design minimaliste** et mobile-responsive
- **Interface de type chat** pour les interactions
- **Authentification** complète (inscription/connexion)
- **Historique** des 5 dernières traductions

### Backend
- **API REST** sécurisée avec FastAPI
- **Authentification JWT** avec validation des tokens
- **Base de données** PostgreSQL avec SQLAlchemy ORM
- **Endpoints prêts** pour l'intégration d'API IA externes

### Prêt pour l'IA
- **Structure d'appel** préparée pour les modèles NLP externes
- **Variables d'environnement** pour l'URL de l'API IA
- **Simulation** des réponses pour le développement

## 🔌 Intégration API IA

Pour intégrer votre modèle IA NLP externe :

1. **Modifiez les endpoints** dans `backend/main.py` :
   - Décommentez les appels HTTP vers `settings.ai_model_url`
   - Adaptez le format des requêtes/réponses selon votre API

2. **Configurez l'URL** dans `.env` :
   ```env
   AI_MODEL_URL=https://votre-api-ia.com
   ```

## 🛡️ Sécurité

- **Mots de passe** hachés avec bcrypt
- **Tokens JWT** pour l'authentification
- **Validation** des données avec Pydantic
- **CORS** configuré pour le frontend

## 📱 Interface Mobile

L'interface est entièrement responsive et optimisée pour :
- **Smartphones** (portrait/paysage)
- **Tablettes**
- **Ordinateurs de bureau**

## 🚧 Développement

### Structure du projet
```
Chatbootsérère/
├── backend/
│   ├── main.py              # Application FastAPI
│   ├── models.py            # Modèles SQLAlchemy
│   ├── schemas.py           # Schémas Pydantic
│   ├── auth.py              # Logique d'authentification
│   ├── database.py          # Configuration DB
│   ├── config.py            # Configuration
│   └── requirements.txt     # Dépendances Python
├── frontend/
│   ├── src/
│   │   ├── components/      # Composants React
│   │   ├── contexts/        # Contextes React
│   │   ├── services/        # Services API
│   │   └── App.tsx          # Application principale
│   └── package.json         # Dépendances Node.js
└── README.md
```

## 📄 Licence

Ce projet est sous licence MIT.
