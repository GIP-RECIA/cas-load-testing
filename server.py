"""
Serveur python simulant un proxy dans le cadre de l'obtention des PGT et PT pour les tests de montée en charge
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

# Dictionnaire mémorisant le PGT associé au PGTIOU
pgtiou_to_pgt = {}

class RequestHandler(BaseHTTPRequestHandler):
    """
    Classe RequestHandler pour répondre aux différentes requêtes
    """
    def do_GET(self):
        """
        Réponse aux requêtes GET, 2 requêtes possibles :
        - Soit le serveur CAS envoie une requête au proxy et on attend en retour juste un code 200,
        mais il ne faut pas oublier d'enregistrer l'association PGTIOU -> PGT
        - Soit le script de test envoie une requête afin de récupérer le PGT car il n'a connassance que
        du PGTIOU via le serveur CAS. Dans ce cas il faut lui donner le PGT et supprimer l'association dans le
        dictionnaire car on n'en a plus besoin
        """
        # Serveur CAS qui envoie une requête au proxy
        if '/proxyValidate' in self.path:
            if self.path != "/proxyValidate":
                params = self.path[22:len(self.path)].split("&pgtId=")
                pgtiou_to_pgt[params[0]] = params[1]
                print(pgtiou_to_pgt)
            self.send_response(200)
            self.end_headers()
        # Script de test qui envoie une requête au proxy
        elif '/getPGT' in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            pgtiou = self.path.split("?pgtiou=")[1]
            response_content = pgtiou_to_pgt[pgtiou]
            del pgtiou_to_pgt[pgtiou]
            self.wfile.write(response_content.encode('utf-8'))
        # Autrement on renvoie un 404 
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404 Not Found')

def run(server_class=HTTPServer, handler_class=RequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting server on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
