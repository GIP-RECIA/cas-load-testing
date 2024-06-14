from __future__ import print_function
import csv
import os
import random
import re
import urllib3
import time
import requests
from urllib.parse import parse_qs, urlparse, unquote
from locust import HttpUser, between, task
from locust.exception import InterruptTaskSet
import logging

# Pour résoudre l'erreur "Too many open files" quand on fait trop de connexions
import resource
resource.setrlimit(resource.RLIMIT_NOFILE, (99999, 99999))
print(resource.getrlimit(resource.RLIMIT_NOFILE))

# Pour tester avec un certificat autosigné
IGNORE_SSL = True

# Expressions régulières utilisées pour chercher dans l'HTML retourné
EXECUTION_PAT = re.compile(r'<input type="hidden" name="execution" value="([^"]+)"')
EVENTID_PAT = re.compile(r'<input type="hidden" name="_eventId" value="([^"]+)"')

# URL du/des faux service(s) à tester
SERVICE = "https://localhost:8009/test"

# Temps min et max entre déconnexion et reconnexion
MIN_TIME_BETWEEEN_SESSIONS = 300
MAX_TIME_BETWEEEN_SESSIONS = 600

# Temps min et max entre connexion et déconnexion (durée de la session)
MIN_TIME_OF_SESSION = 180
MAX_TIME_OF_SESSION = 300

# Nom du fichier contenant les identifiants
CREDENTIALS_FILENAME = "credentials.csv"

# URL du serveur CAS
CAS_URL = "https://loadcas.test.recia.dev"

# URL du serveur proxy utilisé pour récuéprer le PGT
PROXY_URL = "http://cas2:8000"

# Niveau de log et fichier de log
LOGGING_LEVEL = logging.ERROR
LOGGING_FILE = "logs/locust.log"

# Conf relative aux logs
logging.basicConfig(
    level=LOGGING_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGGING_FILE),
        logging.StreamHandler()
    ]
)

# Chargement des login/password
def load_creds(filename):
    """
    Chargement des identifiants de test via un fichier csv
    """
    credpath = os.path.join(
        os.path.dirname(__file__),
        filename)
    creds = []
    with open(credpath, "r") as f:
        reader = csv.reader(f)        
        for row in reader:
            creds.append((row[0], row[1]))
    return creds
CREDS = load_creds(CREDENTIALS_FILENAME)


class CASLocust(HttpUser):
    """
    Classe représentant un utilisateur (une session)
    """
    # Temps entre chaque tâche
    wait_time = between(MIN_TIME_BETWEEEN_SESSIONS, MAX_TIME_BETWEEEN_SESSIONS)
    
    def on_start(self):
        """
        Méthode appelée une seule fois lors de la création de l'utilisateur
        """
        self.client.base_url = CAS_URL
        # On choisi un couple login/password au hasard
        cred = random.choice(CREDS)
        self.username = cred[0]
        self.password = cred[1]
        if IGNORE_SSL:
            urllib3.disable_warnings()

    @task
    def login(self):
        """
        Tâche principale qui a pour but de reproduire un flot pour une authentification CAS
        """
        logging.debug(f"CAS login process starting for {self.username}")

        # 1- Le service redirige l'utilisateur non connecté vers la page de connexion du CAS
        cas_response = self.client.get("/cas/login?service="+SERVICE,
                                  name="1. /cas/login - GET",
                                  verify=False)
        content = cas_response.text
        logging.debug(f"Got answer for 1. /cas/login - GET for {self.username}")

        # Si on nous présente la page après connexion, alors pas besoin de se reconnecter (ne devrait pas arriver normalement)
        found_exec = EXECUTION_PAT.search(content)
        if found_exec is None:
            logging.error(f"User {self.username} already logged in")
            logging.error(f"HTML content: {content}")
            logging.error(f"Code : {cas_response.status_code}")
            raise InterruptTaskSet()
        
        # Sinon on essaie de se connecter
        else:
            execution = found_exec.groups()[0]
            found_eventid = EVENTID_PAT.search(content)
            if found_eventid is None:
                logging.error(f"Incorrect login page for {self.username}: no eventId field found on login form")
                logging.error(f"HTML content: {content}")
                raise InterruptTaskSet()
            event_id = found_eventid.groups()[0]

            # On prépare ce qui est nécéssaire à la requête de connexion
            data = {
                "username": self.username,
                "password": self.password,
                "execution": execution,
                "_eventId": event_id,
                "geolocation": "",
            }

            # Le temps que l'utilisateur tape ses identifiants
            time.sleep(random.randint(1,4))

            logging.debug(f"Sending 2. /cas/login - POST for {self.username}")

            # 2- L'utilisateur s'authentifie au CAS via son login/password car il n'est pas encore connecté
            cas_login_response = self.client.post("/cas/login?service="+SERVICE,
                                            data=data,
                                            name="2. /cas/login - POST",
                                            verify=False,
                                            allow_redirects=False)

            logging.debug(f"Got answer for 2. /cas/login - POST for {self.username}")

            # cas_login_response est la requête de redirection vers le service (avec le TGT déjà dans les cookies)
            # cas_login_response.next est la réponse vers le service avec le ST dans l'URL
            if cas_login_response.status_code == 302:

                logging.debug(f"User {self.username} logged in successfully")
                
                # On récupère le ST dans l'URL
                cas_ticket = cas_login_response.next.url.split(SERVICE+"?ticket=")[1]

                # 3.1 Le service fait valider le ST par le cas pour valider l'authentification
                # Pour la première validation de ST, comme on est censé passer par le portail on va faire générer un PGT
                with self.client.get("/cas/serviceValidate",
                                            params={'service': SERVICE, 'ticket': cas_ticket, 'pgtUrl': PROXY_URL+"/proxyValidate"},
                                            name="3.1 /cas/serviceValidate (proxy) - GET",
                                            verify=False,
                                            catch_response=True) as ticket_response:

                    logging.debug(f"Got answer for 3.1. /cas/serviceValidate - GET for {self.username}")

                    ticket_status = ticket_response.status_code
                    assert ticket_status == 200, "CAS Ticket response code of: ".format(ticket_status)

                    user_data = ticket_response.text

                    if "<cas:authenticationSuccess>" and "<cas:proxyGrantingTicket>" in user_data:
                        logging.debug(f"ST validated for user {self.username}, now generating PGT")
                        # Récupération du PGTIOU
                        pgtiou = user_data.split("<cas:proxyGrantingTicket>")[1].split("</cas:proxyGrantingTicket>")[0]
                        logging.debug("PGTIOU extract : "+pgtiou)

                        # Ici le proxy reçoit d'abord une requête de la part du CAS du type GET /proxyValidate?pgtIou=PGTIOU-6-XXXX&pgtId=PGT-6-XXXX HTTP/1.1 et répond en code 200
                        # Ensuite le serveur CAS répond à la requête initiale avec un XML qui contient un PGTIOU
                        # Dans notre cas le proxy est a moitié joué par un petit serveur python, et à moitié joué par ce script de test donc on ne voit que la moitié de la réponse
                        # Il faut donc récupérer le PGT grâce au PGTIOU en faisant une requête au proxy (qui ne dépend donc pas du serveur CAS, pas de monitoring ici)
                        proxy_answer = requests.get(PROXY_URL+"/getPGT?pgtiou="+pgtiou, verify=False, allow_redirects=False)
                        pgt = proxy_answer.text
                        logging.debug("Proxy -> PGT answer : "+pgt)

                        # 3.2 Accès à une ressource protégée via le proxy -> le proxy fait une requête au serveur CAS
                        # Ici on reproduit un comportement simillaire à la réalité ou on accède à 3 ressources
                        for i in range(3):
                            with self.client.get("/cas/proxy",
                                                    params={'pgt': pgt, 'targetService': SERVICE},
                                                    name="3.2. /cas/proxy - GET",
                                                    verify=False,
                                                    catch_response=True) as proxy_resource:
                    
                                # La réponse est un PT pour le service auquel on veut accéder
                                logging.debug(f"Got answer for 3.2. /cas/proxy - GET for {self.username}")
                                pt = proxy_resource.text.split("cas:proxyTicket>")[1]
                                pt = pt[:len(pt)-2]
                                logging.debug("pt extract : "+pt)
                                if "<cas:proxySuccess>" in proxy_resource.text:
                                    # 3.3 Ensuite le proxy fait une requête à l'app avec le ST pour que l'app requete le CAS pour faire valider son ST
                                    with self.client.get("/cas/proxyValidate",
                                                            params={'service': SERVICE, 'ticket': pt},
                                                            name="3.3. /cas/proxyValidate - GET",
                                                            verify=False,
                                                            catch_response=True) as proxy_validate:
                                        # On vérifie si la réponse est bonne
                                        logging.debug(f"Got answer for 3.3. /cas/proxyValidate - GET for {self.username}")
                                        if "<cas:authenticationSuccess>" not in proxy_validate.text:
                                            proxy_validate.failure("Validation de PT impossible")
                                            raise InterruptTaskSet()
                                else:
                                    proxy_resource.failure("Création de PT impossible")
                                    raise InterruptTaskSet()

                    else:
                        logging.error(f"ST validation failed for user {self.username}")
                        logging.error(f"HTML content: {user_data}")
                        ticket_response.failure("Ticket invalide")
                        raise InterruptTaskSet()
                
                # Temps de la session CAS
                cas_session_time = random.randint(MIN_TIME_OF_SESSION,MAX_TIME_OF_SESSION)
                # Nombre de service auxquels on va accéder pendant la session CAS
                service_validate_count = random.randint(4,6)

                # On va refaire valider un certain nombre de ST pendant le temps de la session CAS
                for i in range(service_validate_count):
                    time.sleep(cas_session_time/service_validate_count)

                    # On envoie un GET sur /cas/login mais cette fois-ci avec le cookie, dont on se connecte directement
                    with self.client.get("/cas/login?service="+SERVICE,
                            name="4. /cas/login - GET",
                            verify=False,
                            allow_redirects=False,
                            catch_response=True) as cas_login_get_response:
                        
                        logging.debug(f"Got answer for 4. /cas/login - GET for {self.username}")

                        if cas_login_get_response.status_code == 302:
                            logging.debug(f"User {self.username} logged in successfully")
                            
                            # On récupère le ST dans l'URL
                            cas_ticket = cas_login_get_response.next.url.split(SERVICE+"?ticket=")[1]

                            # Le service fait valider le ST par le cas pour valider l'authentification
                            with self.client.get("/cas/serviceValidate",
                                                        params={'service': SERVICE, 'ticket': cas_ticket},
                                                        name="5. /cas/serviceValidate - GET",
                                                        verify=False,
                                                        catch_response=True) as ticket_response:

                                logging.debug(f"Got answer for 5. /cas/serviceValidate - GET for {self.username}")

                                ticket_status = ticket_response.status_code
                                assert ticket_status == 200, "CAS Ticket response code of: ".format(ticket_status)

                                user_data = ticket_response.text
                                if "<cas:authenticationSuccess>" in user_data:
                                    logging.debug(f"ST validated for user {self.username}")
                                else:
                                    logging.error(f"ST validation failed for user {self.username}")
                                    logging.error(f"HTML content: {user_data}")
                                    ticket_response.failure("Ticket invalide")
                                    raise InterruptTaskSet()

                        # Si on n'obtient pas un redirect, ce n'est pas normal       
                        else:
                            logging.error(f"{self.username} not logged in ?")
                            logging.error(f"HTML content : {cas_login_get_response.text}")
                            cas_login_get_response.failure("User disconnected or not connected")
                            raise InterruptTaskSet()

                # On reste connecté au cas encore un certain temps avant de se déconnecter
                time.sleep(cas_session_time/service_validate_count)

                # Puis on se déconnecte
                self.client.get("/cas/logout",
                    verify=False,
                    name="6. /cas/logout - GET")

                logging.debug(f"User {self.username} logged out successfully")

            else:
                logging.error(f"Login failed for user {self.username}")
                logging.error(f"HTML content: {cas_login_response.text}")
                raise InterruptTaskSet()


    def on_stop(self):
        """
        Méthode appelée une seule fois lors de la destruction de l'utilisateur (une fois les tests terminés)
        Ici on s'assure juste que l'utilisateur est bien déconnecté (on réparti les déconnexions sur 5 minutes)
        """
        time.sleep(random.randint(1,120))
        self.client.get("/cas/logout",
                verify=False,
                name="6. /cas/logout - GET")
        logging.debug(f"User {self.username} logged out successfully")
