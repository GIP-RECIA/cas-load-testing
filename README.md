# Tests de montée en charge

Les tests de montée en charge prennent la forme d'un script python utilisant la librairie locust.
L'objectif de ce script est simple : simuler les différentes requêtes qu'un client CAS pourrait faire au serveur CAS et mesurer les temps de réponse du serveur CAS.

## Présentation du script

Le principe de locust est du script est le suivant : des utilisateurs vont être générés au fil du temps. Une fois qu'un utilisateur est généré, il peut réaliser plusieurs tâches.
Une tâche correspond à un ensemble de requêtes envoyées au serveur CAS et simulant le comportement d'un réél utilisateur.
Chaque requête est traquée par locust, de sorte à mesurer son temps d'éxécution, mais aussi si la réponse est correcte (si ce n'est pas le cas, une erreur est levée).
Un utilisateur (pour locust) correspond à un fil d'éxécution qui va réaliser les tâches qui lui sont confiées. Les utilisateurs sont indépendants les uns des autres.
Dans notre cas, un utilisateur pour locust correspond à un utilisateur pour CAS (chaque utilisateur locust a un mot de passe et login différent).
Le script est basé sur un script fourni par directement par CAS : https://github.com/apereo/cas/blob/master/etc/loadtests/locust/cas/casLocust.py

Le script contient 2 tâches :
- Une tâche avec un flot d'authentification complet (de la saisie des indentifiants jusqu'au logout final)
- Une tâche servant uniquement à faire le logout, appelée lorsque les tests sont terminées afin de nettoyer le ticket registry

La tâche principale est la tâche avec le flot d'authentification complet. Cette tâche va être appellée en boucle par l'utilisateur (avec un certain délai entre deux éxécutions).
Elle contient tout d'abord la phase de "première connexion" :
- Un GET sur `/login`, simulant un utilisateur qui arrive sur le CAS
- Un petit délai simulant l'utilisateur qui entre ses identifiants
- Un POST sur `/login`, simulant un utilisateur qui clique sur se connecter après avoir saisi ses identifiants
- Un GET sur `/serviceValidate`, simulant le client CAS qui fait valider son ST auprès du serveur CAS
**Important** : Le service simulé est un service autorisé à fonctionner en proxy (comme le portail), on va donc faire faire un ensemble de requêtes qu'on ne fait que dans ce mode précis (pour simuler le fonctionnement du portail)
Dans notre cas le fonctionnement du script est particulier car il doit jouer le rôle du navigateur web de l'utilisateur, mais aussi du client CAS et du proxy (car on a besoin de récuperer le PGT).
On réalise ensuite 3 fois de suite et sans délai :
- Un GET sur `/proxy` pour simuler un serveur qui voudrait réaliser une autentification CAS à travers le proxy (le portail)
- Un GET sur `/proxyValidate` pour simuler un serveur qui voudrait faire valider son PT
Ensuite, on passe dans la phase de "nouvelle connexion", autrement dit la réutilisation de son TGT pour accéder à d'autres services.
Pour cela, on répète un certain nombre de fois, avec un certain délai entre les répétitions, les deux requpetes suivantes :
- Un GET sur `/login`, simulant un service qui redirige vers cet URL avec le TGT comme cookie car l'utilisateur est déjà authentifié auprès du CAS
- Un GET sur `/serviceValidate`, simulant le client CAS qui fait valider son ST auprès du serveur CAS
Enfin, on se déconnecte avec :
- Un GET sur `/logout`, simulant soit l'utilisateur qui termine sa session CAS en se déconnectant
Une fois que toutes ces requêtes ont été effectuées, on peut donc recommencer la tâche principale (avec le même utilisateur).

### Focus sur la partie proxy
Afin de pouvoir réaliser correctement les requêtes de génération des PGT, on a besoin d'un serveur qui joue le rôle de proxy.
Celui-ci est amené à être installé sur la même machine ou tournent le ou les serveurs CAS car il sera contacté via localhost (selon la définition des services et les paramètres passés lors du serviceValidate).
Ce serveur va être à la fois requêté par le serveur CAS, qui va lui transmettre le PGT et le PGTIOU (il attend alors une réponse 200 OK), mais aussi par le script, qui n'obtient que que le PGTIOU et pas le PGT de la part du CAS.
Ainsi, ce serveur garde en mémoire un dictionnaire associant les PGTIOU aux PGT et écoute sur 2 routes :
- /proxyValidate ou il reçoit les requêtes du serveur CAS
- /getPGT ou il reçoit les requetes du script locust

### Script utilitaire de génération d'utilisateurs de test
Un script annexe `generate_users.py` est utilisé pour générer un ldif avec les utilisateurs de test (pour le docker ldap) et un csv que le script locust prend en entrée comme liste des utilisateurs de test (avec uniquement login/mdp). Le fichier ldif sera à mettre dans `.docker/bootstrap/ldif/custom` dans le docker-openldap. Le fichier csv est lui à laisser dans le répertoire où il est.

### Définition du service de test
Le script locust fait valider des ST, PT et génère des PGT. Il a donc besoin de venir d'un service reconnu par le CAS. La définition du service de test utilisé (coté CAS) est la suivante :
```json
{
    "@class" : "org.apereo.cas.services.CasRegisteredService",
    "serviceId" : "^https:\/\/localhost:8009\/.*",
    "name" : "Service Test Client Cas",
    "description": "Test description",
    "id" : 15749872,
    "logoutType" : "BACK_CHANNEL",
    "logoutUrl" : "https://localhost:8009/logout",
    "proxyPolicy" : {
        "@class" : "org.apereo.cas.services.RegexMatchingRegisteredServiceProxyPolicy",
        "pattern" : ".*",
        "useServiceId": false,
        "exactMatch": false
    }
}
```

### Paramètres du script locust
| Nom | Signification |
|--|--|
| IGNORE_SSL | Booléen pour tester avec un certificat autosigné ou non |
| SERVICE | URL du faux service à tester (voir le serviceId de la définition de service) |
| MIN_TIME_BETWEEEN_SESSIONS | Temps minimum entre deux sessions CAS (entre déconnexion et reconnexion) |
| MAX_TIME_BETWEEEN_SESSIONS | Temps maximum entre deux sessions CAS (entre déconnexion et reconnexion) |
| MIN_TIME_OF_SESSION | Temps minimum d'une session CAS (entre connexion et déconnexion) |
| MAX_TIME_OF_SESSION | Temps maximum d'une session CAS (entre connexion et déconnexion) |
| CREDENTIALS_FILENAME | Chemin vers le fichier csv contenant les identifiants des utilisateurs de test|
| CAS_URL | URL du serveur CAS à tester |
| PROXY_URL | URL du serveur de proxy utilisé pour tester la génération des PGT|
| LOGGING_LEVEL | Niveau de log |
| LOGGING_FILE | Chemin vers le fichier de log |


## Préparation de l'environnement Python
### Coté client (script)
Cloner le repo qui contient les scripts de test python
```bash
git clone locust
```

Installer pyenv (`https://github.com/pyenv/pyenv`) et créer un envrionnement python en 3.11.X avec nommé locust.

Installer locust dedans : 
```bash
pip install locust
```

### Coté serveur (CAS)
Comme expliqué plus haut, on a besoin d'un serveur qui joue le rôle de proxy pour les tests de montée en charge au moment de la génération des PGT.
Le serveur est écrit en python et se trouve dans le fichier `server.py`. Pour le mettre en place, il suffit de le lancer sur la même machine ou tourne le serveur CAS avec :
```bash
python3 server.py
```


## Préparation du LDAP

Afin de tester les performances du serveur CAS dans son ensemble, un LDAP est utilisé comme méthode d'authentification. Celui-ci contient un ensemble de comptes de test, nommés test1, test2, testX, ...
Ces comptes de test possèdent également des attributs que le serveur CAS doit retourner afin de tester les performances dans ce cas de figure.
L'installation et le lancement du serveur LDAP se fait avec docker et un simple :
```bash
docker-compose up
```


## Lancement du script

Activer l'environnement python dans lequel locust est installé :
```bash
pyenv activate locust
```

Lancer le serveur web locust ;
```bash
locust -f cas/casLocust.py --host=HOST --skip-log-setup
```
L'interface web de locust est alors disponible à l'adresse `http://localhost:8089`

A ce moment on peut régler le nombre d'utilisateurs générés par seconde, le nombre d'utilisateurs total (une fois ce nombre atteint il n'y aura plus de nouveaux utillisateurs générés), et la durée du test.
Il suffit alors d'appuyer sur le bouton `Start swarming` pour lancer les requêtes.


## Lecture des résultats

Une fois l'éxécution du script terminé (et même pendant son exécution), on peut consulter la page de lecture des résultats. Celle-ci donne plusieurs informations qui permettent de mesurer si le serveur CAS tient ou non la montée en charge, notamment :
- Une page `Statistics` qui donne des informations pour chaque requête. On surveillera particulièrement le nombre de fails, le temps median et le temps moyen
- Une page `Charts` avec un graphique (celui en bas) qui donne des informations sur l'évolution du temps de réponse des requêtes au fil du temps
