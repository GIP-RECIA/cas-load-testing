"""
Script python permettant de tester le protocole OAuth sur le serveur CAS
"""

import requests
import urllib3
import re
import base64
import time

# Fonctions utiles pour print en même temps que la requête
def get_print(session, url, verify=True, allow_redirects=True):
    print("\n---------------------------------------------------")
    print("Cookies avant requête : "+str(session.cookies.keys()))
    print("Requête : GET "+url)
    response = session.get(url, verify=verify, allow_redirects=allow_redirects)
    print("Code de retour : "+str(response.status_code))
    print("Cookies après requête : "+str(session.cookies.keys()))
    #print(session.cookies.get("DISSESSIONOauthOidcServerSupport"))
    print("---------------------------------------------------")
    return response

def post_print(session, url, data, headers, verify=True, allow_redirects=True):
    print("\n---------------------------------------------------")
    print("Cookies avant requête : "+str(session.cookies.keys()))
    print("Requête : POST "+url)
    response = session.post(url, data=data, headers=headers, verify=verify, allow_redirects=allow_redirects)
    print("Code de retour : "+str(response.status_code))
    print("Cookies après requête : "+str(session.cookies.keys()))
    #print(session.cookies.get("DISSESSIONOauthOidcServerSupport"))
    print("---------------------------------------------------")
    return response

# Initialisation
EXECUTION_PAT = re.compile(r'<input type="hidden" name="execution" value="([^"]+)"')
EVENTID_PAT = re.compile(r'<input type="hidden" name="_eventId" value="([^"]+)"')
urllib3.disable_warnings()
session = requests.session()
message_bytes = "client:secret".encode()
basic_token = base64.b64encode(message_bytes)

#1. Démarrage du flot d'authentification
r1 = get_print(session,
               'https://cas.test.recia.dev/cas/oauth2.0/authorize?response_type=code&redirect_uri=https://cas.test.recia.dev/cas&client_id=client&scope=profile',
               verify=False, allow_redirects=False)
login_url = r1.next.url

#2. Affichage du formulaire de login
r2 = get_print(session, login_url, verify=False)
execution = EXECUTION_PAT.search(r2.text).groups()[0]
event_id = EVENTID_PAT.search(r2.text).groups()[0]

# Si on supprime ce cookie alors la suite du flot ne se passe pas comme prévu et aucun OC n'est retourné
#session.cookies.pop("DISSESSIONOauthOidcServerSupport")

#3. Saisie et envoi des identifiants
login_data = {"username": "test1", "password": "test", "execution": execution, "_eventId": event_id}
r3 = post_print(session, login_url, data=login_data, headers={}, verify=False, allow_redirects=False)

#4. Validation du ST
r4 = get_print(session, r3.next.url, verify=False, allow_redirects=False)

#5. Obtention du OC
r5 = get_print(session, r4.next.url, verify=False, allow_redirects=False)
oc = r5.next.url.split("https://cas.test.recia.dev/cas?code=")[1]

#6. Obtention des token grâce au OC
r6 = post_print(session, "https://cas.test.recia.dev/cas/oauth2.0/token?client_id=client&client_secret=secret&redirect_uri=https://cas.test.recia.dev/cas&grant_type=authorization_code&code="+oc,
                data={}, headers={}, verify=False, allow_redirects=False)
r6_body = r6.json()
print(r6.text)
access_token = r6_body["access_token"]
refresh_token = r6_body["refresh_token"]
print("OLD access : "+access_token)
print(refresh_token)

#7. Obtention d'un nouvel AC grâce au RT
r7 = post_print(session,"https://cas.test.recia.dev/cas/oauth2.0/accessToken?client_id=client&client_secret=secret&grant_type=refresh_token&refresh_token="+refresh_token,
                data={}, headers={}, verify=False, allow_redirects=False)
new_access_token = r7.json()["access_token"]
print(r7.text)
print("NEW access : "+new_access_token)

#8. On peut donc révoquer l'ancien car on n'en a plus besoin
revoke_headers = {"Authorization":"Basic Y2xpZW50OnNlY3JldA=="}
r8 = post_print(session,"https://cas.test.recia.dev/cas/oauth2.0/revoke?&token="+access_token,
                data={}, headers=revoke_headers, verify=False, allow_redirects=False)
print(r8.text)

#9. Test de l'introspection
print(str(basic_token))
introspection_headers = {"Authorization":"Basic Y2xpZW50OnNlY3JldA=="}
r9 = post_print(session,"https://cas.test.recia.dev/cas/oauth2.0/introspect?&token="+new_access_token,
                data={}, headers=introspection_headers, verify=False, allow_redirects=False)
print(r9.text)