# 🎮 Discord Value List Bot

Un bot Discord complet pour gérer une liste de valeurs d'items, des sondages de prix,
un système de trading et bien plus encore.

---

## ✨ Fonctionnalités

### 🔍 Consultation
- Afficher la valeur d'un item avec `/value`
- Lister tous les items triés par valeur avec `/list`
- Rechercher des items par filtres avec `/search`
- Comparer deux items côte à côte avec `/compare`
- Calculer la valeur d'un échange avec `/calculator`
- Consulter l'historique de modifications avec `/history`

### 📊 Sondages
- Créer un sondage de valeur avec `/createpoll`
- Les membres peuvent proposer une valeur via un bouton
- La moyenne est calculée en temps réel
- Fermeture du sondage et mise à jour automatique avec `/closepoll`

### 💰 Trading
- Enregistrer un échange avec `/logtrade`
- Consulter son historique d'échanges avec `/tradehistory`
- Analyser le marché avec `/market`

### 🔔 Surveillance & Alertes
- Suivre un item avec `/watch` (notification DM à chaque modification)
- Définir une alerte de prix avec `/setalert`
- Gérer ses favoris avec `/addfavorite`, `/viewfavorites`, `/removefavorite`

### 👤 Profils & Classements
- Profil utilisateur avec niveau, badges et statistiques via `/profile`
- Classements des meilleurs contributeurs, traders, votants via `/leaderboard`
- Heatmap de distribution des items via `/heatmap`

### 🗺️ Localisation de Coffres
- Trouver un coffre par son nom avec `/locatechest`
- Lister tous les coffres disponibles avec `/locatechestlist`

### ✏️ Contributions
- Proposer l'ajout d'un item avec `/additem`
- Suggérer une modification avec `/suggestmodify`
- Validation par réaction ✅ / ❌ (owner ou rôle autorisé)

### 👑 Administration
- Ajout direct d'items avec `/adminadd`
- Modification et suppression avec `/edititem`, `/deleteitem`
- Sauvegarde et restauration avec `/backup`, `/loadbackup`
- Import/export JSON avec `/importjson`, `/exportjson`
- Annonces globales avec `/announce`
- Gestion des utilisateurs avec `/banuser`, `/resetprofile`
- Tableau de bord complet avec `/dashboard`, `/globalstats`
- Et bien plus...

---

## 📦 Installation

### Prérequis
- Python 3.10 ou supérieur
- Un bot Discord avec les intents activés

### Étapes

**1. Cloner le repository**
```bash
git clone https://github.com/ton-user/ton-repo.git
cd ton-repo
