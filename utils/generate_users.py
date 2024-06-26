"""
Module python permettant de :
- Créer un fichier ldif (31-people.ldif) contenant NB_USERS utilisateurs de test pour un LDAP
- Créer un fichier csv (credentials.csv) contenant NB_USERS utilisateurs de test pour le script locust
"""

# Nombre d'utilisateurs à générer
NB_USERS = 8000

print("Génération du CSV en cours...")

l = []
for i in range(1,NB_USERS):
    l.append(f"test{i}")

f = open("credentials.csv", "w+")
for user in l:
    f.write(f"{user},test\n")
f.close()

print("CSV généré !")

print("Génération du ldif en cours...")

f = open("31-people.ldif", "w+")
s = "version: 1\n"
for i in range(1,NB_USERS):
    print(i)
    s = f"""
dn: uid=F{i}abc,ou=people,dc=esco-centre,dc=fr
objectClass: eduMember
objectClass: ESCOEleveAddons
objectClass: ESCOAddons
objectClass: ENTPerson
objectClass: ENTEleve
cn: TEST TEST
ENTEleveClasses: ENTStructureSIREN=19290009000015,ou=structures,dc=esco-cent
 re,dc=fr$TS2
ENTEleveFiliere: TERMINALE GENERALE
ENTEleveLibelleMEF: TERMINALE SCIENTIFIQUE SVT
ENTEleveMajeur: O
ENTEleveMEF: 20211010110
ENTEleveNivFormation: TERMINALE GENERALE & TECHNO YC BT
ENTEleveStatutEleve: SCOLAIRE
ENTPersonJointure: AC-RENNES$2
ENTPersonLogin: test{i}
sn: TEST
displayName: Test TEST
ENTEleveBoursier: N
ENTEleveCodeEnseignements: 006600
ENTEleveCodeEnseignements: 062900
ENTEleveCodeEnseignements: 043800
ENTEleveCodeEnseignements: 062300
ENTEleveCodeEnseignements: 061300
ENTEleveCodeEnseignements: 030201
ENTEleveCodeEnseignements: 030602
ENTEleveCodeEnseignements: 043700
ENTEleveCodeEnseignements: 010300
ENTEleveCodeEnseignements: 100100
ENTEleveCodeEnseignements: 008400
ENTEleveEnseignements: ACCOMPAGNEMENT PERSONNALISE
ENTEleveEnseignements: SCIENCES DE LA VIE ET DE LA TERRE
ENTEleveEnseignements: ENSEIGNEMENT MORAL ET CIVIQUE
ENTEleveEnseignements: PHYSIQUE-CHIMIE
ENTEleveEnseignements: MATHEMATIQUES
ENTEleveEnseignements: ANGLAIS LV1
ENTEleveEnseignements: ESPAGNOL LV2
ENTEleveEnseignements: HISTOIRE-GEOGRAPHIE
ENTEleveEnseignements: PHILOSOPHIE
ENTEleveEnseignements: EDUCATION PHYSIQUE ET SPORTIVE
ENTEleveEnseignements: VIE DE CLASSE
ENTEleveRegime: DEMI-PENSIONNAIRE DANS L'ETABLISSEMENT 4
ENTEleveStructRattachId: 1085439
ENTEleveTransport: N
ENTPersonAutresPrenoms: Test
ENTPersonDateNaissance: 01/01/1999
ENTPersonGARIdentifiant: 5ae4d2e8-7ead-4bcb-ad15-6dd44b1cf030
ENTPersonNomPatro: TEST
ENTPersonProfils: National_ELV
ENTPersonProfils: National_1
ENTPersonSexe: M
ENTPersonStructRattach: ENTStructureSIREN=19290009000015,ou=structures,dc=es
 co-centre,dc=fr
ESCODomaines: lycees.netocentre.fr
ESCOEleveCodeEnseignements: 006600$ACCOMPAGNEMENT PERSONNALISE
ESCOEleveCodeEnseignements: 062900$SCIENCES DE LA VIE ET DE LA TERRE
ESCOEleveCodeEnseignements: 043800$ENSEIGNEMENT MORAL ET CIVIQUE
ESCOEleveCodeEnseignements: 062300$PHYSIQUE-CHIMIE
ESCOEleveCodeEnseignements: 061300$MATHEMATIQUES
ESCOEleveCodeEnseignements: 030201$ANGLAIS LV1
ESCOEleveCodeEnseignements: 030602$ESPAGNOL LV2
ESCOEleveCodeEnseignements: 043700$HISTOIRE-GEOGRAPHIE
ESCOEleveCodeEnseignements: 010300$PHILOSOPHIE
ESCOEleveCodeEnseignements: 100100$EDUCATION PHYSIQUE ET SPORTIVE
ESCOEleveCodeEnseignements: 008400$VIE DE CLASSE
ESCOEleveVecteurIdentite: 3|||1037745|0290009C
ESCOPersonEtatCompte: INVALIDE
ESCOPersonListeRouge: FALSE
ESCOPersonProfils: ELEVE
ESCOSIREN: 19290009000015
ESCOSIRENCourant: 19290009000015
ESCOUAI: 0290009C
ESCOUAICourant: 0290009C
ESCOUAIRattachement: 0290009C
givenName: Test
isMemberOf: esco:Applications:Folios:DE L IROISE_0290009C
isMemberOf: esco:Etablissements:DE L IROISE_0290009C:TERMINALE GENERALE et T
 ECHNO YC BT:Eleves_TS2
isMemberOf: esco:Etablissements:DE L IROISE_0290009C:Tous_DE L IROISE
isMemberOf: esco:Etablissements:DE L IROISE_0290009C:Eleves
isMemberOf: esco:admin:mediacentre:GAR:UTILISATEUR:DE L IROISE_0290009C
isMemberOf: esco:Applications:mediacentre:GAR:DE L IROISE_0290009C
mail: test.test@test.com
personalTitle: M
uid: F{i}abc
userPassword: test
"""

    f.write(s)
f.close()

print("ldif généré !")