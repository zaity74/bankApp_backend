from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound, MethodNotAllowed
import json
import mysql.connector
import random
import string

# Configuration de la base de données
db_config = {
    'user': 'root',
    'password': 'root',
    'host': 'localhost',
    'database': 'banking_system'
}

# Database connector test
try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT DATABASE();")
    database_name = cursor.fetchone()
    print("Connected to database:", database_name)
    cursor.close()
    conn.close()
except mysql.connector.Error as err:
    print("Error:", err)

# Fonction pour générer un IBAN
def generate_iban():
    return 'FR' + ''.join(random.choices(string.digits, k=30))

# Fonction pour enregistrer un nouvel utilisateur
def register_user(post_data):
    user = json.loads(post_data)
    user['iban'] = generate_iban()
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (nom, prenom, email, password, solde, iban) VALUES (%s, %s, %s, %s, %s, %s)',
                       (user['nom'], user['prenom'], user['email'], user['password'], user['solde'], user['iban']))
        conn.commit()
        user['id'] = cursor.lastrowid
        cursor.close()
        conn.close()
        del user['password']
        return 201, user
    except mysql.connector.Error as err:
        return 500, {'error': str(err)}

# Fonction pour se connecter
def login_user(post_data):
    login_data = json.loads(post_data)
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (login_data['email'], login_data['password']))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            del user['password']
            return 200, user
        else:
            return 404, {'error': 'Invalid email or password'}
    except mysql.connector.Error as err:
        return 500, {'error': str(err)}

# Fonction pour effectuer un virement
def make_transfer(post_data):
    transfer_data = json.loads(post_data)
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('SELECT solde FROM users WHERE iban = %s', (transfer_data['sender_iban'],))
        sender_solde = cursor.fetchone()[0]
        if sender_solde >= transfer_data['amount']:
            cursor.execute('UPDATE users SET solde = solde - %s WHERE iban = %s', (transfer_data['amount'], transfer_data['sender_iban']))
            cursor.execute('UPDATE users SET solde = solde + %s WHERE iban = %s', (transfer_data['amount'], transfer_data['receiver_iban']))
            cursor.execute('INSERT INTO transactions (sender_iban, receiver_iban, amount) VALUES (%s, %s, %s)',
                           (transfer_data['sender_iban'], transfer_data['receiver_iban'], transfer_data['amount']))
            conn.commit()
            cursor.close()
            conn.close()
            return 200, {'message': 'Transfer successful'}
        else:
            return 400, {'error': 'Insufficient funds'}
    except mysql.connector.Error as err:
        return 500, {'error': str(err)}

# Fonction pour commander un chéquier
def order_checkbook(user_iban):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('SELECT solde FROM users WHERE iban = %s', (user_iban,))
        solde = cursor.fetchone()[0]
        if (solde is not None) and (solde >= 15.00):
            cursor.execute('UPDATE users SET solde = solde - 15.00 WHERE iban = %s', (user_iban,))
            conn.commit()
            cursor.close()
            conn.close()
            return 200, {'message': 'Checkbook ordered'}
        else:
            return 400, {'error': 'Insufficient funds'}
    except mysql.connector.Error as err:
        return 500, {'error': str(err)}

# Fonction de gestion pour la route de test
def handle_test_route(request):
    static_data = {
        'message': 'This is a test route',
        'status': 'success',
        'data': [1, 2, 3, 4, 5]
    }
    return Response(json.dumps(static_data), status=200, mimetype='application/json')

# Routes POST
def handle_register_user(request):
    post_data = request.get_data(as_text=True)
    status, response = register_user(post_data)
    return Response(json.dumps(response), status=status, mimetype='application/json')

def handle_login_user(request):
    post_data = request.get_data(as_text=True)
    status, response = login_user(post_data)
    return Response(json.dumps(response), status=status, mimetype='application/json')

def handle_make_transfer(request):
    post_data = request.get_data(as_text=True)
    status, response = make_transfer(post_data)
    return Response(json.dumps(response), status=status, mimetype='application/json')

def handle_order_checkbook(request):
    post_data = request.get_data(as_text=True)
    user_data = json.loads(post_data)
    status, response = order_checkbook(user_data['iban'])
    return Response(json.dumps(response), status=status, mimetype='application/json')

# URL Mapping
url_map = Map([
    Rule('/api/users/register', endpoint='register_user', methods=['POST', 'OPTIONS']),
    Rule('/api/users/login', endpoint='login_user', methods=['POST', 'OPTIONS']),
    Rule('/api/transfer', endpoint='make_transfer', methods=['POST', 'OPTIONS']),
    Rule('/api/checkbook', endpoint='order_checkbook', methods=['POST', 'OPTIONS']),
    Rule('/api/test', endpoint='test_route', methods=['GET', 'OPTIONS'])  # Nouvelle route de test
])

def application(environ, start_response):
    request = Request(environ)
    urls = url_map.bind_to_environ(environ)
    try:
        endpoint, args = urls.match()
        if request.method == 'OPTIONS':
            response = Response(status=200)
        elif endpoint == 'register_user':
            response = handle_register_user(request)
        elif endpoint == 'login_user':
            response = handle_login_user(request)
        elif endpoint == 'make_transfer':
            response = handle_make_transfer(request)
        elif endpoint == 'order_checkbook':
            response = handle_order_checkbook(request)
        elif endpoint == 'test_route':  # Nouvelle route de test
            response = handle_test_route(request)
        else:
            response = Response('Not Found', status=404)
    except (HTTPException, MethodNotAllowed) as e:
        response = Response(str(e), status=e.code)
    response = add_cors_headers(response)  # Ajouter les en-têtes CORS
    return response(environ, start_response)

# Gestion des en-têtes CORS
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple('localhost', 7000, application)
