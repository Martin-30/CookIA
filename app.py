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
                st.success(f"{nom.capitalize()} ajouté au frigo !")
                st.rerun()

    st.divider()
    st.subheader("Mon Frigo Actuel")
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
        liste_frigo = ", ".join([f"{item['quantite']} {item['unite']} de {item['nom']}" for item in aliments]) if aliments else "Le frigo est vide."
    except:
        liste_frigo = "Erreur de lecture du frigo."

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
                        "Tu es CookIA, un assistant cuisinier sympa pour un utilisateur vivant seul et très occupé. "
                        f"INVENTAIRE DU FRIGO : {liste_frigo}. "
                        f"MENU DE LA SEMAINE EN COURS (MÉMOIRE) : {texte_menu_actuel}. "
                        "CONTRAINTES MATÉRIELLES : L'utilisateur n'a PAS de four, ni de mixeur. 2 plaques de cuisson et un micro-ondes. "
                        "CONTRAINTES DE TEMPS : Propose de cuire des bases en double (pâtes, riz, patates) pour les réutiliser le lendemain. "
                        "Si l'utilisateur te demande de l'aide pour cuisiner, base-toi sur le MENU DE LA SEMAINE EN COURS. "
                        "IMPORTANT : À la TOUTE FIN de ta réponse, si tu proposes un NOUVEAU menu, tu DOIS inclure un bloc JSON contenant strictement la liste des ingrédients manquants à acheter :\n"
                        "```json\n"
                        "[\n"
                        "  {\"nom\": \"Tomates\", \"quantite\": 4, \"unite\": \"pièce(s)\"}\n"
                        "]\n"
                        "```\n"
                        "S'il ne manque rien ou si on discute juste cuisine, renvoie un tableau vide `[]`."
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
                        st.session_state.courses_proposees = json.loads(match_json.group(1))
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

            # 2. Sauvegarde du texte de l'IA dans la base de données (Mémoire)
            supabase.table("menu_semaine").insert({
                "contenu": st.session_state.texte_proposition_ia
            }).execute()

            st.session_state.courses_proposees = [] 
            st.session_state.texte_proposition_ia = ""
            st.success("Menu validé ! Tes courses sont dans l'appli Google Tasks sur ton téléphone.")
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
                
                # On filtre manuellement pour ne garder que celles qui sont cochées
                taches_terminees = [t['title'] for t in taches if t.get('status') == 'completed']
                
            if not taches_terminees:
                st.warning("Aucun article n'a été coché dans ta 'Liste de course'.")
            else:
                with st.spinner("Le Chef trie tes courses (et met la lessive de côté)... 🧠"):
                    try:
                        # 1. Le Prompt pour filtrer avec l'IA
                        liste_text = ", ".join(taches_terminees)
                        prompt_filtre = f"""
                        Voici une liste d'articles que je viens d'acheter : {liste_text}.
                        1. Retire absolument tous les produits d'hygiène, d'entretien ou non comestibles (ex: dentifrice, sacs poubelle, savon).
                        2. Garde UNIQUEMENT les produits alimentaires et déduis-en une quantité et une unité logique si elles ne sont pas précisées.
                        3. Renvoie le résultat au format JSON strict, sans aucun texte autour, avec cette structure :
                        [
                          {{"nom": "Pommes", "quantite": 4, "unite": "pièce(s)"}},
                          {{"nom": "Lait", "quantite": 1, "unite": "L"}}
                        ]
                        S'il n'y a aucun produit alimentaire, renvoie [].
                        """
                        
                        reponse_ia = client.chats.create(model="gemini-3.6-flash").send_message(prompt_filtre)
                        texte_json = re.sub(r"```json\n.*?\n```", "", reponse_ia.text, flags=re.DOTALL) # Nettoyage si l'IA met des balises
                        match = re.search(r'\[.*\]', reponse_ia.text, re.DOTALL)
                        
                        if match:
                            articles_alimentaires = json.loads(match.group(0))
                        else:
                            articles_alimentaires = json.loads(reponse_ia.text) # Si le texte brut est déjà le JSON
                        
                        # 2. Insertion dans le Garde-Manger (Supabase)
                        for article in articles_alimentaires:
                            supabase.table("inventaire").insert({
                                "nom": str(article.get("nom", "")).capitalize(),
                                "quantite": float(article.get("quantite", 1.0)),
                                "unite": str(article.get("unite", "pièce(s)"))
                            }).execute()
                            
                        # 3. Nettoyage de Google Tasks (efface toutes les tâches terminées)
                        service.tasks().clear(tasklist=list_id).execute()
                        
                        # 4. Affichage du résumé
                        st.success("✅ Courses rangées avec succès et Google Tasks nettoyé !")
                        st.write("**Ajouté au Garde-Manger :**")
                        for art in articles_alimentaires:
                            st.write(f"- {art['quantite']} {art['unite']} de {art['nom']}")
                            
                    except Exception as e:
                        st.error(f"Erreur lors du traitement par l'IA : {e}")

    # Ajout manuel de secours (au cas où on oublie de l'ajouter sur le téléphone)
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
# PAGE 4 : MENU DE LA SEMAINE (NOUVEAU)
# ==========================================
elif st.session_state.page_actuelle == "📅 Menu de la semaine":
    st.subheader("📅 Tes Recettes Prévues")
    st.info("Voici le menu que tu as validé. L'IA s'en souvient : tu peux aller dans l'Assistant et lui demander des conseils pour préparer ces plats !")
    
    try:
        menus = supabase.table("menu_semaine").select("*").order("created_at", desc=True).execute().data
        if not menus:
            st.success("Aucun menu en cours. Demande à l'IA de t'en générer un !")
        else:
            # On affiche uniquement le dernier menu généré
            menu_actuel = menus[0]
            st.markdown(menu_actuel['contenu'])
            
            st.divider()
            if st.button("🗑️ Semaine terminée : Effacer ce menu", type="primary"):
                # On nettoie la base de données
                supabase.table("menu_semaine").delete().eq("id", menu_actuel['id']).execute()
                # On vide aussi l'historique du chat pour repartir à zéro
                st.session_state.messages = []
                st.success("Menu archivé ! Tu peux en générer un nouveau.")
                st.rerun()
    except Exception as e:
        st.error(f"Erreur de lecture du menu : {e}")
