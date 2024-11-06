from flask import Flask, render_template, abort, request, redirect, url_for, make_response, jsonify
from dotenv import load_dotenv
import jwt
import os
import mysql.connector # Had to use mysql.connector due to issues with mac and mysqldb
from werkzeug.utils import secure_filename

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv('JWT_KEY')
app.config["UPLOAD_FOLDER"] = "static/files"
app.config['UPLOAD_EXTENSIONS'] = ['.jpg','.pdf','.png', '.jpeg']
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 # Setting to 10 MB limit

# MySQL configurations
db_config = {
    'user': 'root',  
    'password': 'password',  
    'host': '127.0.0.1',
    'database': 'test_schema'  
}


@app.route('/')
def main():
    JWT_token = request.cookies.get('JWT')
    if JWT_token:
        try:
            data = protected()
            return redirect(url_for('profile', username=data['username']))
        except jwt.ExpiredSignatureError:
            return redirect(url_for('signin'))
        except jwt.InvalidTokenError:
            return redirect(url_for('signin'))
    return render_template('login.html')


@app.route('/gallery')
def gallery():
    files = get_all_images()
    return render_template('gallery.html', files = files)


@app.route('/allimages')
def get_all_images():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM files")
        files = cursor.fetchall()
        return files
    except:
        return []
    finally:
        if conn.is_connected:
            conn.close()
            cursor.close()


@app.route('/profile/<username>')
def profile(username):
    if not request.cookies.get('JWT'):
        abort(401)
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM files WHERE user = %s", (username,))
        files = cursor.fetchall()

        return render_template('profile.html', username=username, files=files)

    except:
        return render_template('profile.html', username=username)
    finally:
        if conn.is_connected:
            conn.close()
            cursor.close()


@app.route('/image/<fileID>')
def image_viewer(fileID):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM files WHERE fileid = %s", (fileID,))
        file = cursor.fetchone()

        cursor.execute("SELECT * FROM users WHERE username = %s", (file.get('user'), ))
        user = cursor.fetchone()

        token = request.cookies.get('JWT')
        cur_user = ""

        if token:
            cur_user = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return render_template("image.html", file=file, user=user, cur_user=cur_user)
        
        return render_template("image.html", file=file, user=user, cur_user=cur_user)
    except mysql.connector.Error as err:
        print(err)
        abort(404)


@app.route('/signin', methods=['POST', 'GET'])
def signin(message = ""):
    JWT_token = request.cookies.get('JWT')
    if JWT_token:
        data = protected()
        return redirect(url_for('profile', username=data['username']))
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()

        if user:
            resp = make_response(redirect(url_for('profile', username=user['username'])))
            token = jwt.encode({'ID': user["id"], 'username': username}, app.config["SECRET_KEY"])
            resp.set_cookie('JWT', token)
            return resp
        else:
            message = 'Incorrect Information, please try again'
    return render_template('login.html', message = message)       


@app.route('/login', methods=["POST"])
def login():
    username = request.form['username']
    password = request.form['password']
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        if user:
            resp = make_response('Cookie is created')
            token = jwt.encode({'ID': user["id"], 'username': username}, app.config["SECRET_KEY"])
            resp.set_cookie('JWT', token)
            return token
        else:
            return jsonify({"message": "Could not find user with these credentials"}), 404
    except:
        return jsonify({"message": "Could not find user with these credentials"}), 404
    finally:
        if conn.is_connected:
            conn.close()
            cursor.close()


@app.route('/register', methods=['POST', 'GET'])
def register():
    message = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            message = "Please fill in all Fields"
            render_template('register.html', message = message)
        elif check_username(username):
            message = "This username is already taken"
            render_template('register.html', message = message)
        else:
            try: 
                conn = get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", 
                            (username, password))
                conn.commit()
                return redirect(url_for("signin"))
            except mysql.connector.Error as err:
                return f"Error: {err}"
            finally:
                if conn.is_connected:
                    conn.close()
                    cursor.close()
    return render_template('register.html', message = message)


@app.route('/settings', methods=['GET'])
def settings():
    message = ""
    data = protected()
    if not data:
        abort(401)
    return render_template('settings.html', data=data, message=message)


@app.route('/get_user', methods=["GET"])
def get_user(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (id, ))
        user = cursor.fetchone()
        return jsonify(user)

    except:
        return jsonify({'message': "Could not find user"})
    finally:
        if conn.is_connected:
            conn.close()
            cursor.close()


@app.route('/update', methods=['POST'])
def update_user():
    data = protected()
    new_username = request.form.get('username')
    if check_username(new_username):
        return jsonify({"message": "Username taken"}), 401
    

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE users SET username = %s WHERE id = %s", (new_username, data['ID']))
        conn.commit()
        return jsonify({"message": "Username updated successfully"}), 200

    except:
        return jsonify({'message': "Could not update"}), 401

    finally:
        if conn.is_connected:
            conn.close()
            cursor.close()


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    resp = make_response(redirect(url_for('main')))
    resp.set_cookie('JWT', '', expires=0)
    return resp


# File Uploading
@app.route('/uploadFile', methods=['POST', 'GET'])
def uploadFile():
    if not request.cookies.get('JWT'):
        abort(401)
    return render_template("upload.html")


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    uploaded_file = request.files['file']
    if uploaded_file.filename != '':
        filename = secure_filename(uploaded_file.filename)
        file_size = uploaded_file.content_length
        if os.path.splitext(filename)[1] in app.config['UPLOAD_EXTENSIONS']:
            if file_size <= app.config["MAX_CONTENT_LENGTH"]:
                uploaded_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                create_file_data(filename)
                return jsonify({"message": "File" + filename + " has been uploaded successfully"})
            else:
                return jsonify({"message": "File" + filename + "File size exceeds the maximum"})
        else:
            return jsonify({"message": "File" + filename + "Please put in an acceptable file type"})


@app.route('/delete/files/<fileid>', methods=["POST"])
def delete_file(fileid):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM files WHERE fileid = %s", (fileid,))
        file = cursor.fetchone()
        
        token = request.cookies.get('JWT')

        if token:
            cur_user = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            if cur_user['username'] == file['user']:
                cursor.execute("DELETE FROM files WHERE fileid = %s", (fileid,))
                conn.commit()
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file['name'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                return redirect(url_for('main'))
            else:
                abort(401)
        else:
            abort(401)
    except Exception as e:
        print(e)
        abort(401)
    finally:
        if conn.is_connected():
            conn.close()
            cursor.close()


# Protected route to check if JWT token is correct
@app.route('/protected', methods=['GET'])
def protected():
    token = request.cookies.get('JWT')
    if not token:
        return jsonify({'message': 'Token is missing!'}), 403
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return data
    except:
        resp = make_response(redirect(url_for('signin'), message="Invalid Token, please log in"))
        resp.set_cookie('JWT', '', expires=0)
        return jsonify({'message': 'Invalid credentials'}), 401


# All Error Handlers
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


# Returns mysql Connection
def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        app.logger.error(f"Database connection error: {err}")
        return None
    
# Returns if username is found within MySQL database
def check_username(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        print("User found was: " + str(user))
        return user is not None

    except mysql.connector.Error as err:
        print(err)
        return False
    finally:
        if conn.is_connected:
            conn.close()
            cursor.close()


# File Updating Helper Functions
def create_file_data(filename):
    token = request.cookies.get("JWT")
    data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("INSERT INTO files (name, user) VALUES (%s, %s)", 
                       (filename, data["username"]))
        conn.commit()
        print("File " + filename + " was saved to database under " + data["username"])
        return True

    except mysql.connector.Error as err:
        print(err)
        return False
    finally:
        if conn.is_connected:
            conn.close()
            cursor.close()


if __name__ == '__main__':
    app.run()