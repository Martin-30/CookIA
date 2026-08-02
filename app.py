import os
import re
import json
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
from supabase import create_client, Client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 1. Chargement et Connexion
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Configuration de la page
st.set_page_config(page_title="CookIA", page_icon="🍳", layout="centered")
st.title("🍳 CookIA - Ton Assistant")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

def get_tasks_service():
    """Initialise la connexion à Google Tasks de manière sécurisée."""
    try:
        # On lit le token depuis les secrets de Streamlit ou le .env local
        token_str = st.secrets.get("GOOGLE_TASKS_TOKEN") or os.getenv("GOOGLE_TASKS_TOKEN")
        if token_str:
            creds_data = json.loads(token_str)
            creds = Credentials.from_authorized_user_info(creds_data)
            return build('tasks', 'v1', credentials=creds)
    except Exception as e:
        st.error(f"Problème de connexion à Google Tasks : {e}")
    return None

def get_or_create_shopping_list(service, list_name="Liste de course"):
    """Cherche la liste exacte ou la crée si elle n'existe pas."""
    results = service.tasklists().list().execute()
    items = results.get('items', [])
    for task_list in items:
        if task_list['title'] == list_name:
            return task_list['id']
    # Si la liste n'existe pas encore sur ton compte Google, on la crée
    new_list = service.tasklists().insert(body={'title': list_name}).execute()
    return new_list['id']

# 2. Initialisation des mémoires
if "messages" not in st.session_state:
    st.session_state.messages = []
if "courses_proposees" not in st.session_state:
    st.session_state.courses_proposees = []
if "texte_proposition_ia" not in st.session_state:
    st.session_state.texte_proposition_ia = ""
if "page_actuelle" not in st.session_state:
    st.session_state.page_actuelle = "👨‍🍳 Assistant IA"

# ==========================================
# MENU DE NAVIGATION
# ==========================================
with st.sidebar:
    st.header("Menu")
    
    if st.button("📦 Garde-Manger", use_container_width=True, type="primary" if st.session_state.page_actuelle == "📦 Garde-Manger" else "secondary"):
        st.session_state.page_actuelle = "📦 Garde-Manger"
        st.rerun()
        
    if st.button("👨‍🍳 Assistant IA", use_container_width=True, type="primary" if st.session_state.page_actuelle == "👨‍🍳 Assistant IA" else "secondary"):
        st.session_state.page_actuelle = "👨‍🍳 Assistant IA"
        st.rerun()
        
    if st.button("🛒 Courses", use_container_width=True, type="primary" if st.session_state.page_actuelle == "🛒 Courses" else "secondary"):
        st.session_state.page_actuelle = "🛒 Courses"
        st.rerun()

    # NOUVEL ONGLET
    if st.button("📅 Menu de la semaine", use_container_width=True, type="primary" if st.session_state.page_actuelle == "📅 Menu de la semaine" else "secondary"):
        st.session_state.page_actuelle = "📅 Menu de la semaine"
        st.rerun()

# ==========================================
# PAGE 1 : INVENTAIRE
# ==========================================
if st.session_state.page_actuelle == "📦 Garde-Manger":
    st.subheader("Ajouter un ingrédient")
    with st.form("form_ajout", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            nom = st.text_input("Nom", placeholder="ex: Tomates, Œufs...")
        with col2:
            # MODIFICATION : step=1.0 pour avancer de 1 en 1
            quantite = st.number_input("Qté", min_value=0.1, value=1.0, step=1.0)
        with col3:
            unite = st.selectbox("Unité", ["pièce(s)", "g", "kg", "ml", "L", "boîte(s)"])
            
        if st.form_submit_button("Ajouter"):
            if nom.strip() != "":
                supabase.table("inventaire").insert({"nom": nom.capitalize(), "quantite": quantite, "unite": unite}).execute()
                st.success(f"{nom.capitalize()} ajouté au garde-manger !")
                st.rerun()

    st.divider()
    st.subheader("Mon Garde-Manger Actuel")
    try:
        aliments = supabase.table("inventaire").select("*").order("created_at", desc=True).execute().data
        if not aliments:
            st.info("Ton inventaire est vide.")
        else:
            for item in aliments:
                # MODIFICATION : Ratio de colonnes optimisé pour mobile et alignement vertical
                col_texte, col_bouton = st.columns([0.85, 0.15], vertical_alignment="center")
                with col_texte:
                    st.markdown(f"**{item['nom']}** : {item['quantite']} {item['unite']}")
                with col_bouton:
                    if st.button("❌", key=f"del_inv_{item['id']}"):
                        supabase.table("inventaire").delete().eq("id", item['id']).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Erreur : {e}")

# ==========================================
# PAGE 2 : ASSISTANT IA
# ==========================================
elif st.session_state.page_actuelle == "👨‍🍳 Assistant IA":
    st.subheader("👨‍🍳 Ton Chef Cuistot Virtuel")
    
    # Lecture de l'inventaire et du menu (inchangé)
    try:
        aliments = supabase.table("inventaire").select("*").execute().data
        liste_frigo = ", ".join([f"{item['quantite']} {item['unite']} de {item['nom']}" for item in aliments]) if aliments else "Le garde-manger est vide."
    except:
        liste_frigo = "Erreur de lecture du grade-manger."

    try:
        menu_actif = supabase.table("menu_semaine").select("*").order("created_at", desc=True).limit(1).execute().data
        texte_menu_actuel = menu_actif[0]['contenu'] if menu_actif else "Aucun menu n'est actuellement prévu ou validé."
    except:
        texte_menu_actuel = "Erreur de lecture du menu."

    # 1. B我們TON DE GÉNÉRATION
    if st.button("🪄 Générer un nouveau menu (Lundi - Jeudi)"):
        st.session_state.messages = [] # On vide l'historique proprement
        st.session_state.prompt_en_attente = "Génère un menu de 4 repas simples pour la semaine (du lundi au jeudi). Prends en compte mes contraintes."
        st.rerun()

    # 2. BARRE DE CHAT
    if prompt := st.chat_input("Ex: Je lance le repas de ce soir, rappelle-moi quoi faire !"):
        st.session_state.prompt_en_attente = prompt
        st.rerun()

    # 3. AFFICHAGE DE L'HISTORIQUE (Une seule fois !)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 4. GESTION DE LA RÉFLEXION DE L'IA
    if "prompt_en_attente" in st.session_state and st.session_state.prompt_en_attente:
        prompt_utilisateur = st.session_state.prompt_en_attente
        st.session_state.messages.append({"role": "user", "content": prompt_utilisateur})
        
        with st.chat_message("user"):
            st.markdown(prompt_utilisateur)
            
        with st.chat_message("assistant"):
            with st.spinner("Le Chef CookIA réfléchit... 🍳"):
                try:
                    instruction_systeme = (
                        "Tu es CookIA, un assistant cuisinier sympa, pragmatique et direct. "
                        "Ton utilisateur est un étudiant et apprenti ingénieur très occupé qui vit seul. "
                        f"INVENTAIRE DU GARDE-MANGER : {liste_frigo}. "
                        f"MENU DE LA SEMAINE EN COURS (MÉMOIRE) : {texte_menu_actuel}. "
                        "CONTRAINTES MATÉRIELLES : L'utilisateur n'a PAS de four, ni de mixeur. Uniquement 2 plaques de cuisson et un micro-ondes. "
                        "RYTHME ET HABITUDES : Tu gères UNIQUEMENT les menus du soir. L'utilisateur mange à la cantine le midi : les dîners n'ont donc pas toujours besoin d'être hyper consistants ni de contenir systématiquement de la viande. Ils doivent surtout être simples et rapides. "
                        "GAIN DE TEMPS (BATCH COOKING) : Propose de cuire des bases en double (pâtes, riz, patates) pour les réutiliser le lendemain OU plus tard dans la semaine. "
                        "Si l'utilisateur te demande de l'aide pour cuisiner, base-toi sur le MENU DE LA SEMAINE EN COURS. "
                        "IMPORTANT : À la TOUTE FIN de ta réponse, si tu proposes un NOUVEAU menu, tu DOIS inclure DEUX blocs JSON distincts :\n"
                        "1. Le premier bloc pour les courses manquantes :\n"
                        "```json\n"
                        "{\"courses\": [{\"nom\": \"Tomates\", \"quantite\": 4, \"unite\": \"pièce(s)\"}]}\n"
                        "```\n"
                        "2. Le deuxième bloc pour la consommation du Garde-Manger plat par plat (EXCLUS le sel, poivre, huile, épices de ce déstockage) :\n"
                        "```json\n"
                        "{\"recettes\": [\n"
                        "  {\"titre\": \"Spaghettis Bolognaise\", \"consommation\": [{\"nom\": \"Pâtes\", \"quantite\": 250, \"unite\": \"g\"}, {\"nom\": \"Steak haché\", \"quantite\": 1, \"unite\": \"pièce(s)\"}]}\n"
                        "]}\n"
                        "```\n"
                        "S'il ne s'agit pas d'un nouveau menu complet, renvoie `{\"courses\": []}` et `{\"recettes\": []}`."
                    )
                    
                    historique_gemini = [types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part.from_text(text=m["content"])]) for m in st.session_state.messages[:-1]]
                    
                    chat = client.chats.create(
                        model="gemini-3.6-flash",
                        config=types.GenerateContentConfig(system_instruction=instruction_systeme, temperature=0.7),
                        history=historique_gemini
                    )
                    
                    reponse = chat.send_message(prompt_utilisateur)
                    texte_reponse = reponse.text
                    texte_propre = re.sub(r"```json\n.*?\n```", "", texte_reponse, flags=re.DOTALL).strip()
                    
                    # Enregistrement dans la mémoire
                    st.session_state.messages.append({"role": "assistant", "content": texte_propre})
                    match_json = re.search(r"```json\n(.*?)\n```", texte_reponse, re.DOTALL)
                    if match_json:
                        data_extraite = json.loads(match_json.group(1))
                        # On cible spécifiquement la liste contenue dans "courses"
                        st.session_state.courses_proposees = data_extraite.get("courses", [])
                        st.session_state.texte_proposition_ia = texte_propre

                    # On vide le prompt en attente et on recharge la page pour tout afficher proprement
                    st.session_state.prompt_en_attente = None
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erreur : {e}")
                    st.session_state.prompt_en_attente = None

    # 5. BLOC DE VALIDATION DES COURSES
    if st.session_state.courses_proposees:
        st.divider()
        st.warning("🛒 **L'IA te propose ce menu et ces courses :**")
        for ing in st.session_state.courses_proposees:
            st.markdown(f"- {ing['quantite']} {ing['unite']} de {ing['nom']}")
        
        if st.button("✅ Valider le menu, sauvegarder et envoyer à Google Tasks"):
            # 1. Envoi à Google Tasks
            service = get_tasks_service()
            if service:
                with st.spinner("Synchronisation avec Google Tasks... 📱"):
                    list_id = get_or_create_shopping_list(service, "Liste de course")
                    for ing in st.session_state.courses_proposees:
                        titre_task = f"{ing['quantite']} {ing['unite']} de {ing['nom'].capitalize()}"
                        service.tasks().insert(tasklist=list_id, body={'title': titre_task}).execute()
            else:
                st.warning("⚠️ Google Tasks non connecté. Sauvegarde locale uniquement.")

            # 2. Sauvegarde du texte global
            supabase.table("menu_semaine").insert({
                "contenu": st.session_state.texte_proposition_ia
            }).execute()

            # 3. Extraction et sauvegarde des repas pour le déstockage
            try:
                match_recettes = re.search(r'\{\s*"recettes"\s*:\s*\[.*?\]\s*\}', st.session_state.texte_proposition_ia, re.DOTALL)
                if match_recettes:
                    data_recettes = json.loads(match_recettes.group(0)).get("recettes", [])
                    # On vide l'ancien programme
                    supabase.table("programme_repas").delete().neq("id", 0).execute()
                    
                    for r in data_recettes:
                        supabase.table("programme_repas").insert({
                            "titre": r.get("titre", "Plat sans nom"),
                            "ingredients_consommes": json.dumps(r.get("consommation", [])),
                            "fait": False
                        }).execute()
            except Exception as e:
                st.warning(f"Erreur lors de l'enregistrement des repas dynamiques : {e}")

            st.session_state.courses_proposees = [] 
            st.session_state.texte_proposition_ia = ""
            st.success("Menu validé ! Tes courses sont dans Google Tasks et tes repas planifiés.")
            st.rerun()

# ==========================================
# PAGE 3 : RETOUR DE COURSES
# ==========================================
elif st.session_state.page_actuelle == "🛒 Courses":
    st.subheader("🛒 Retour de Courses")
    st.info("Coche tes articles directement dans l'application Google Tasks sur ton téléphone quand tu es au magasin. En rentrant, clique ici pour ranger tes achats !")
    
    if st.button("🔄 Synchroniser mes achats depuis Google Tasks", type="primary", use_container_width=True):
        service = get_tasks_service()
        if not service:
            st.error("⚠️ Impossible de se connecter à Google Tasks.")
        else:
            with st.spinner("Lecture de tes achats sur Google Tasks..."):
                list_id = get_or_create_shopping_list(service, "Liste de course")
                
                # Récupère toutes les tâches (y compris les terminées/cachées)
                results = service.tasks().list(tasklist=list_id, showCompleted=True, showHidden=True).execute()
                taches = results.get('items', [])
                
                # MODIFICATION ICI : On garde l'objet entier pour conserver le fameux "id"
                taches_terminees = [t for t in taches if t.get('status') == 'completed']
                
            if not taches_terminees:
                st.warning("Aucun article n'a été coché dans ta 'Liste de course'.")
            else:
                with st.spinner("Le Chef trie tes courses (et met la lessive de côté)... 🧠"):
                    try:
                        # 1. Le Prompt pour filtrer avec l'IA
                        # On extrait juste les titres pour parler à Gemini
                        titres_taches = [t['title'] for t in taches_terminees]
                        liste_text = ", ".join(titres_taches)
                        
                        prompt_filtre = f"""
                        Voici une liste d'articles que je viens d'acheter : {liste_text}.
                        1. Retire absolument tous les produits d'hygiène, d'entretien ou non comestibles (ex: dentifrice, sacs poubelle, savon).
                        2. EXCLUS tous les plats préparés (ex: pizza, plats micro-ondes, petits pains) et les snacks/friandises (ex: Snickers, chips, gâteaux).
                        3. Garde STRICTEMENT les ingrédients bruts ou de base servant à cuisiner des repas (ex: légumes, viandes, riz, pâtes, crème, fromages, épices).
                        4. Déduis-en une quantité et une unité logique si elles ne sont pas précisées.
                        5. Renvoie le résultat au format JSON strict, sans aucun texte autour, avec cette structure :
                        [
                          {{"nom": "Pommes", "quantite": 4, "unite": "pièce(s)"}},
                          {{"nom": "Lait", "quantite": 1, "unite": "L"}}
                        ]
                        S'il n'y a aucun produit alimentaire à cuisiner, renvoie [].
                        """
                        
                        reponse_ia = client.chats.create(model="gemini-3.6-flash").send_message(prompt_filtre)
                        match = re.search(r'\[.*\]', reponse_ia.text, re.DOTALL)
                        
                        if match:
                            articles_alimentaires = json.loads(match.group(0))
                        else:
                            articles_alimentaires = json.loads(reponse_ia.text)
                        
                        # 2. Insertion dans le Garde-Manger (Supabase)
                        for article in articles_alimentaires:
                            supabase.table("inventaire").insert({
                                "nom": str(article.get("nom", "")).capitalize(),
                                "quantite": float(article.get("quantite", 1.0)),
                                "unite": str(article.get("unite", "pièce(s)"))
                            }).execute()
                            
                        # 3. MODIFICATION ICI : Nettoyage chirurgical de Google Tasks
                        for tache in taches_terminees:
                            service.tasks().delete(tasklist=list_id, task=tache['id']).execute()
                        
                        # 4. Affichage du résumé
                        st.success("✅ Courses rangées avec succès et Google Tasks nettoyé !")
                        st.write("**Ajouté au Garde-Manger :**")
                        for art in articles_alimentaires:
                            st.write(f"- {art['quantite']} {art['unite']} de {art['nom']}")
                            
                    except Exception as e:
                        st.error(f"Erreur lors du traitement par l'IA : {e}")

    # Ajout manuel de secours
    st.divider()
    st.write("Un oubli ? Ajoute un article manuellement :")
    with st.form("form_ajout_secours", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            nouvel_article = st.text_input("Article à ajouter à ta prochaine liste")
        with col2:
            submit = st.form_submit_button("Ajouter")
            if submit and nouvel_article.strip():
                service = get_tasks_service()
                if service:
                    list_id = get_or_create_shopping_list(service, "Liste de course")
                    service.tasks().insert(tasklist=list_id, body={'title': nouvel_article.capitalize()}).execute()
                    st.success("Ajouté à Google Tasks !")

# ==========================================
# PAGE 4 : MENU DE LA SEMAINE
# ==========================================
elif st.session_state.page_actuelle == "📅 Menu":
    st.subheader("📅 Programme & Validation des Repas")
    
    st.write("### 🍽️ Repas de la semaine")
    repas_db = supabase.table("programme_repas").select("*").order("id").execute().data
    
    if not repas_db:
        st.info("Aucun repas planifié pour le moment. Demande un menu à l'Assistant !")
    else:
        for repas in repas_db:
            col1, col2 = st.columns([3, 1])
            with col1:
                if repas['fait']:
                    st.write(f"~~**{repas['titre']}**~~ *(Cuisiné)*")
                else:
                    st.write(f"**{repas['titre']}**")
            with col2:
                if not repas['fait']:
                    if st.button("🍽️ Cuisiné !", key=f"repas_{repas['id']}"):
                        # Déstockage dynamique
                        ingredients = json.loads(repas['ingredients_consommes'])
                        inventaire = supabase.table("inventaire").select("*").execute().data
                        
                        for ing in ingredients:
                            nom_ing = ing['nom'].strip().lower()
                            qte_a_retirer = float(ing['quantite'])
                            
                            for item in inventaire:
                                if item['nom'].strip().lower() == nom_ing:
                                    nouvelle_qte = max(0.0, float(item['quantite']) - qte_a_retirer)
                                    if nouvelle_qte == 0:
                                        supabase.table("inventaire").delete().eq("id", item['id']).execute()
                                    else:
                                        supabase.table("inventaire").update({"quantite": nouvelle_qte}).eq("id", item['id']).execute()
                        
                        # Validation du plat
                        supabase.table("programme_repas").update({"fait": True}).eq("id", repas['id']).execute()
                        st.success(f"{repas['titre']} validé ! Garde-Manger mis à jour.")
                        st.rerun()

    st.divider()
    
    st.write("### 📜 Détail complet du menu")
    res = supabase.table("menu_semaine").select("contenu").order("created_at", desc=True).limit(1).execute()
    if res.data:
        st.markdown(res.data[0]["contenu"])
    else:
        st.info("Aucun menu sauvegardé.")
