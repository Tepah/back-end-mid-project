from flask import Flask, render_template, abort, request, redirect, url_for, make_response, jsonify
from dotenv import load_dotenv
import jwt
import os
import mysql.connector # Had to use mysql.connector due to issues with mac and mysqldb

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv('JWT_KEY')

# MySQL configurations
db_config = {
    'user': 'root',  
    'password': 'password',  
    'host': '127.0.0.1',
    'database': 'test_schema'  
}

conn = mysql.connector.connect(**db_config)


@app.route('/')
def main():
    try:
        cursor = conn.cursor()

        JWT_token = request.cookies.get('JWT')
        if JWT_token:
            return redirect(url_for('profile'))
        return render_template('login.html')

        
    except mysql.connector.Error as err:
        return f"Error: {err}"
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


@app.route('/create_account')
def create_account():
    JWT_token = request.cookies.get('JWT')
    if JWT_token:
        return redirect(url_for('profile'))
    return render_template('register.html')


@app.route('/login', methods=['POST'])
def login():
    # TODO: THIS IS NEXT, FUTURE PETE
    username = request.form['username']
    password = request.form['password']


    resp = make_response(redirect(url_for('profile')))
    token = jwt.encode({
        'username': username,
        'password': password
    }, app.config["SECRET_KEY"])
    resp.set_cookie('JWT', token)
    return resp

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    # TODO: Add Errors
    if not username or check_username():
        abort(400)
    
    try: 
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", 
                       (username, password))
        conn.commit()
        return redirect(url_for("login"))
    except mysql.connector.Error as err:
        return f"Error: {err}"
    finally:
        cursor.close()

@app.route('/protected', methods=['GET'])
def protected():
    token = request.cookies.get('JWT')
    if not token:
        return jsonify({'message': 'Token is missing!'}), 403
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return data
    except:
        return jsonify({'message': 'Invalid token'}), 403
    
@app.route('/check_username', methods=["POST"])
def check_username():
    username = request.form['username']
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = " + username)
        user = cursor.fetchone()
        return user is not None

    except mysql.connector.Error as err:
        return False
    finally:
        cursor.close()
    

@app.errorhandler(400)
def bad_request_route(e):
    return render_template('400.html'), 400

@app.errorhandler(401)
def unauthorized(e):
    return render_template('401.html'), 401

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# Testing the error requests
@app.route('/badrequest')
def bad_request_route():
    abort(400)

@app.route('/unauthorized')
def unauthorized_route():
    abort(401)

@app.route('/notfound')
def not_found_route():
    abort(404)

@app.route('/servererror')
def server_error_route():
    abort(500)

if __name__ == '__main__':
    app.run()