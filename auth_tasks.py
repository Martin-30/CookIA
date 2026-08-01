import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Les droits que l'on demande à Google (lire et écrire dans Tasks)
SCOPES = ['https://www.googleapis.com/auth/tasks']

def main():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    # Ceci va ouvrir une page web dans ton navigateur pour te connecter à Google
    creds = flow.run_local_server(port=0)
    
    # On sauvegarde le jeton magique généré
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    print("Succès ! Le fichier token.json a été créé. Ne le mets JAMAIS sur GitHub.")

if __name__ == '__main__':
    main()