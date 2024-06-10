from __future__ import print_function
import csv
import os
import random
import re
import urllib3
import time
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

# URL du ou des serveurs CAS, si on ne teste qu'un serveur mettre deux url identiques ou modifier la liste en conséquence
CAS1_URL = "https://cas1:8443"
CAS2_URL = "https://cas2:8443"
CAS_LIST = [CAS2_URL, CAS2_URL]

# Conf relative aux logs
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/locust.log"),
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

        # On change de serveur CAS
        self.client.base_url = random.choice(CAS_LIST)

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
            """
            logging.error(self.client.cookies.get("TGC"))
            logging.error(type(self.client.cookies.get("TGC")))
            for cookie in self.client.cookies:
                print(cookie)
                print(cookie.domain)
                print(cookie.path)
            """
            domains = self.client.cookies.list_domains()
            if 'cas1.local' not in domains:
                self.client.cookies.set(name="TGC", value=self.client.cookies.get("TGC"), domain="cas1.local", path="/cas")
            if 'cas2.local' not in domains:
                self.client.cookies.set(name="TGC", value=self.client.cookies.get("TGC"), domain="cas2.local", path="/cas")
            """
            for cookie in self.client.cookies:
                print(cookie)
                print(cookie.domain)
                print(cookie.path)
            """
            # cas_login_response est la requête de redirection vers le service (avec le TGT déjà dans les cookies)
            # cas_login_response.next est la réponse vers le service avec le ST dans l'URL
            if cas_login_response.status_code == 302:

                logging.debug(f"User {self.username} logged in successfully")
                
                # On récupère le ST dans l'URL
                cas_ticket = cas_login_response.next.url.split(SERVICE+"?ticket=")[1]

                # On change de serveur CAS
                self.client.base_url = random.choice(CAS_LIST)

                # 3- Le service fait valider le ST par le cas pour valider l'authentification
                with self.client.get("/cas/serviceValidate",
                                            params={'service': SERVICE, 'ticket': cas_ticket},
                                            name="3. /cas/serviceValidate - GET",
                                            verify=False,
                                            catch_response=True) as ticket_response:

                    logging.debug(f"Got answer for 3. /cas/serviceValidate - GET for {self.username}")

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
                
                # Temps de la session CAS
                cas_session_time = random.randint(MIN_TIME_OF_SESSION,MAX_TIME_OF_SESSION)
                # Nombre de service auxquels on va accéder pendant la session CAS
                service_validate_count = random.randint(6,8)

                # On va refaire valider un certain nombre de ST pendant le temps de la session CAS
                for i in range(service_validate_count):
                    time.sleep(cas_session_time/service_validate_count)
                    # On change de serveur CAS
                    self.client.base_url = random.choice(CAS_LIST)

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

                            # On change de serveur CAS
                            self.client.base_url = random.choice(CAS_LIST)

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

                # On change de serveur CAS
                self.client.base_url = random.choice(CAS_LIST)

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
        Ici on s'assure juste que l'utilisateur est bien déconnecté (on répartit les déconnexions sur 5 minutes)
        """
        time.sleep(random.randint(1,120))
        self.client.base_url = random.choice(CAS_LIST)
        self.client.get("/cas/logout",
                verify=False,
                name="6. /cas/logout - GET")
        logging.debug(f"User {self.username} logged out successfully")
