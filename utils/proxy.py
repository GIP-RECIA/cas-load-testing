"""
Script python permettant de tester un service CAS en mode proxy
"""

import requests
import urllib3
import re
import base64
import xml.etree.ElementTree as ET

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

#1. Affichage du formulaire de login
r1 = get_print(session,'https://cas.test.recia.dev/cas/login?service=http://localhost:8000/proxy',
               verify=False, allow_redirects=False)
execution = EXECUTION_PAT.search(r1.text).groups()[0]
event_id = EVENTID_PAT.search(r1.text).groups()[0]

#2. Saisie et envoi des identifiants
login_data = {"username": "test1", "password": "test", "execution": execution, "_eventId": event_id}
r2 = post_print(session, "https://cas.test.recia.dev/cas/login?service=http://localhost:8000/proxy", data=login_data, headers={}, verify=False, allow_redirects=False)
st_url = r2.next.url
print("URL de retour pour validation du ST : "+st_url)
st = st_url.split("?ticket=")[1]

#3. Le proxy fait valider le ST auprès du CAS mais avec un paramètre spécial dans l'URL
r3 = get_print(session, "https://cas.test.recia.dev/cas/serviceValidate?ticket="+st
                +"&service=http://localhost:8000/proxy&pgtUrl=http://localhost:8000/proxyValidate",
                  verify=False, allow_redirects=False)

# Récupération du PGTIOU
print("Réponse : \n"+r3.text)
pgtiou = r3.text.split("<cas:proxyGrantingTicket>")[1].split("</cas:proxyGrantingTicket>")[0]
print("PGTIOU extract : "+pgtiou)

# Ici le proxy reçoit d'abord une requête de la part du CAS du type GET /proxyValidate?pgtIou=PGTIOU-6-XXXX&pgtId=PGT-6-XXXX HTTP/1.1 et répond en code 200
# Ensuite le serveur CAS répond à la requête initiale avec un XML qui contient un PGTIOU
# Dans notre cas le proxy est a moitié joué par un petit serveur python, et à moitié joué par ce script de test donc on ne voit que la moitié de la réponse
# Il faut donc récupérer le PGT grâce au PGTIOU
r3_v2 = get_print(session, "http://maquette-java:8000/getPGT?pgtiou="+pgtiou, verify=False, allow_redirects=False)
pgt = r3_v2.text
print("Réponse PGT : "+pgt)

#4. Accès à une ressource protégée via le proxy -> le proxy fait une requête au serveur CAS
r4 = get_print(session, "https://cas.test.recia.dev/cas/proxy?pgt="+pgt
                +"&targetService=http://localhost:8000/resource",
                  verify=False, allow_redirects=False)
# La réponse est un PT pour le service auquel on veut accéder
print("Réponse : \n"+r4.text)
st = r4.text.split("cas:proxyTicket>")[1]
st = st[:len(st)-2]
print(st)

#5. Ensuite le proxy fait une requête à l'app avec le ST pour que l'app requete le CAS pour faire valider son PT
r5 = get_print(session, "https://cas.test.recia.dev/cas/proxyValidate?service=http://localhost:8000/resource&ticket="+st,
                  verify=False, allow_redirects=False)
# On vérifie si la réponse est bonne
print(r5.text)

#6. Après à partir de là on a juste des communications entre le proxy et l'app, donc plus rien dans cette partie