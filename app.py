import os
import re
import json
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
from supabase import create_client, Client

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
    
    if st.button("📦 Inventaire", use_container_width=True, type="primary" if st.session_state.page_actuelle == "📦 Inventaire" else "secondary"):
        st.session_state.page_actuelle = "📦 Inventaire"
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
if st.session_state.page_actuelle == "📦 Inventaire":
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
    
    # 1. Lecture de l'inventaire
    try:
        aliments = supabase.table("inventaire").select("*").execute().data
        liste_frigo = ", ".join([f"{item['quantite']} {item['unite']} de {item['nom']}" for item in aliments]) if aliments else "Le frigo est vide."
    except:
        liste_frigo = "Erreur de lecture du frigo."

    # 2. Lecture du menu en cours (La mémoire de l'IA)
    try:
        menu_actif = supabase.table("menu_semaine").select("*").order("created_at", desc=True).limit(1).execute().data
        texte_menu_actuel = menu_actif[0]['contenu'] if menu_actif else "Aucun menu n'est actuellement prévu ou validé."
    except:
        texte_menu_actuel = "Erreur de lecture du menu."

    def interroger_ia(prompt_utilisateur):
        st.session_state.messages.append({"role": "user", "content": prompt_utilisateur})
        with st.chat_message("user"):
            st.markdown(prompt_utilisateur)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            with st.spinner("Le Chef CookIA réfléchit... 🍳"):
                try:
                    # INJECTION DE LA MÉMOIRE DANS LE PROMPT
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
                    message_placeholder.markdown(texte_propre)
                    st.session_state.messages.append({"role": "assistant", "content": texte_propre})

                    match_json = re.search(r"```json\n(.*?)\n```", texte_reponse, re.DOTALL)
                    if match_json:
                        st.session_state.courses_proposees = json.loads(match_json.group(1))
                        st.session_state.texte_proposition_ia = texte_propre # On garde le texte de la recette en mémoire

                except Exception as e:
                    message_placeholder.error(f"❌ Erreur : {e}")

    if st.button("🪄 Générer un nouveau menu (Lundi - Jeudi)"):
        st.session_state.messages = [] # On vide le chat pour repartir au propre
        interroger_ia("Génère un menu de 4 repas simples pour la semaine (du lundi au jeudi). Prends en compte mes contraintes.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ex: Je lance le repas de ce soir, rappelle-moi quoi faire !"):
        interroger_ia(prompt)

    if st.session_state.courses_proposees:
        st.divider()
        st.warning("🛒 **L'IA te propose ce menu et ces courses :**")
        for ing in st.session_state.courses_proposees:
            st.markdown(f"- {ing['quantite']} {ing['unite']} de {ing['nom']}")
        
        if st.button("✅ Valider le menu, sauvegarder les recettes et envoyer aux Courses"):
            # 1. Envoi à la liste de courses
            for ing in st.session_state.courses_proposees:
                supabase.table("liste_courses").insert({
                    "nom": str(ing.get("nom", "")).capitalize(),
                    "quantite": float(ing.get("quantite", 1)),
                    "unite": str(ing.get("unite", "pièce(s)"))
                }).execute()
            
            # 2. Sauvegarde du texte de l'IA dans la base de données (Mémoire)
            supabase.table("menu_semaine").insert({
                "contenu": st.session_state.texte_proposition_ia
            }).execute()

            st.session_state.courses_proposees = [] 
            st.session_state.texte_proposition_ia = ""
            st.success("Menu validé ! Il est désormais dans l'onglet 'Menu de la semaine'.")
            st.rerun()

# ==========================================
# PAGE 3 : COURSES
# ==========================================
elif st.session_state.page_actuelle == "🛒 Courses":
    st.subheader("🛒 Ma Liste de Courses")
    
    with st.form("form_ajout_course", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            nom_c = st.text_input("Article")
        with col2:
            qte_c = st.number_input("Qté", min_value=0.1, value=1.0, step=1.0) # step=1.0 ici aussi
        with col3:
            unite_c = st.selectbox("Unité", ["pièce(s)", "g", "kg", "ml", "L", "boîte(s)"], key="u_course")
            
        if st.form_submit_button("Ajouter à la liste"):
            if nom_c.strip() != "":
                supabase.table("liste_courses").insert({"nom": nom_c.capitalize(), "quantite": qte_c, "unite": unite_c}).execute()
                st.rerun()

    st.divider()
    
    try:
        courses = supabase.table("liste_courses").select("*").order("created_at", desc=True).execute().data
        if not courses:
            st.info("Ta liste est vide !")
        else:
            for item in courses:
                col_nom, col_qte, col_btn_buy, col_btn_del = st.columns([2, 1.2, 1.2, 0.6], vertical_alignment="center")
                
                with col_nom:
                    st.markdown(f"**{item['nom']}** <br> *(en {item['unite']})*", unsafe_allow_html=True)
                
                with col_qte:
                    nouvelle_qte = st.number_input("Qté finale", value=float(item['quantite']), step=1.0, key=f"edit_{item['id']}")
                
                with col_btn_buy:
                    if st.button("✅", key=f"buy_{item['id']}", help="Acheté"):
                        supabase.table("inventaire").insert({
                            "nom": item['nom'],
                            "quantite": nouvelle_qte, 
                            "unite": item['unite']
                        }).execute()
                        supabase.table("liste_courses").delete().eq("id", item['id']).execute()
                        st.rerun()
                        
                with col_btn_del:
                    if st.button("❌", key=f"del_c_{item['id']}"):
                        supabase.table("liste_courses").delete().eq("id", item['id']).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Erreur : {e}")

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
