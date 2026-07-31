# 🍳 CookIA - Assistant de Cuisine Intelligent

CookIA est une application web personnelle créée avec Streamlit, Supabase et l'API Gemini. Elle permet de gérer l'inventaire de sa cuisine, d'interagir avec un assistant IA pour planifier 4 repas par semaine (du lundi au jeudi), de mettre à jour automatiquement ses stocks et d'exporter sa liste de courses.

## 🚀 Fonctionnalités
- **Inventaire en temps réel :** Suivi des ingrédients de cuisine (ajout/suppression manuelle).
- **Chat Assistant Cuistot :** Propose 4 repas par semaine selon l'inventaire actuel et tes envies.
- **Auto-déduction :** Réduction automatique des stocks et mise à jour de la liste de courses lors de la validation d'une recette.
- **Export Google Tasks :** Synchronisation de la liste de courses sur mobile.

## 🛠️ Tech Stack
- **Langage :** Python 3.11
- **Interface :** Streamlit
- **Base de données :** Supabase (PostgreSQL)
- **IA :** Google Gemini API (via AI Studio)

## 📦 Installation & Lancement local

1. Activer l'environnement Conda :
   ```bash
   conda activate cookia
