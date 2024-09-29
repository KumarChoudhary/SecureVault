from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_mysqldb import MySQL
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  # MySQL username
app.config['MYSQL_PASSWORD'] = ''  # MySQL password
app.config['MYSQL_DB'] = 'my_database'  # MySQL database name

mysql = MySQL(app)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def load_user_data(username):
    cur = mysql.connection.cursor()
    cur.execute('SELECT colors, image_path, password FROM users WHERE username = %s', (username,))
    data = cur.fetchone()
    cur.close()
    if data:
        colors = data[0].split(",")
        img_path = data[1]
        password = data[2]
        return colors, img_path, password
    else:
        return None, None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        colors = request.form.getlist('colors')
        image = request.files['image']

        if username and password and colors and image:
            # Check if username already exists
            cur = mysql.connection.cursor()
            cur.execute('SELECT username FROM users WHERE username = %s', (username,))
            existing_user = cur.fetchone()

            if existing_user:
                flash("Username already exists, choose a different one.", "error")
                cur.close()
            else:
                # Save the image file
                filename = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
                image.save(filename)

                try:
                    cur.execute('INSERT INTO users (username, password, colors, image_path) VALUES (%s, %s, %s, %s)',
                                (username, password, ",".join(colors), filename))
                    mysql.connection.commit()
                    flash("User registered successfully!", "success")
                    return redirect(url_for('index'))
                except Exception as e:
                    flash(f"An error occurred: {e}", "error")
                finally:
                    cur.close()
        else:
            flash("Registration failed. Please fill out all fields and select both colors and an image.", "error")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username and password:
            cur = mysql.connection.cursor()
            cur.execute('SELECT password FROM users WHERE username = %s', (username,))
            data = cur.fetchone()
            cur.close()

            if data:
                # Username exists, now check the password
                if data[0] == password:
                    session['username'] = username
                    return redirect(url_for('two_factor'))  # Redirect to two-factor authentication
                else:
                    flash("Username or password incorrect!", "error")
            else:
                flash("Username not found!", "error")
        else:
            flash("Please fill out all fields.", "error")
    return render_template('index.html')

@app.route('/two_factor', methods=['GET', 'POST'])
def two_factor():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = session['username']
        selected_colors = request.form.getlist('colors')
        selected_image = request.files['image']
        if selected_colors and selected_image:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], selected_image.filename)
            selected_image.save(filename)

            stored_colors, stored_img_path = load_user_data(username)[:2]
            if stored_colors and stored_img_path:
                if selected_colors == stored_colors and filename == stored_img_path:
                    flash("Authentication successful!", "success")
                    return redirect(url_for('dashboard'))  # Redirect to dashboard on success
                else:
                    flash("Color and image authentication failed!", "error")
            else:
                flash("No user data found. Please register first.", "warning")
        else:
            flash("Authentication failed. Please fill out all fields and select both colors and an image.", "error")
    return render_template('two_factor.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        color1 = request.form['color1']
        color2 = request.form['color2']
        color3 = request.form['color3']
        image = request.files['image']

        cur = mysql.connection.cursor()
        cur.execute('SELECT password, colors, image_path FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()

        if user:
            stored_password, stored_colors, stored_image_path = user
            stored_colors = stored_colors.split(',')

            if [color1, color2, color3] == stored_colors:
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
                image.save(image_path)

                if stored_image_path == image_path:
                    os.remove(image_path)  # Remove the uploaded image
                    return render_template('forgot_password.html', password=stored_password)
                else:
                    os.remove(image_path)  # Remove the uploaded image
                    flash('Image does not match.', 'error')
            else:
                flash('Colors do not match.', 'error')
        else:
            flash('Username not found.', 'error')

    return render_template('forgot_password.html')


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    else:
        flash("You need to login first.", "warning")
        return redirect(url_for('index'))

@app.route('/add_password', methods=['GET', 'POST'])
def add_password():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        app_name = request.form['app_name']
        username = request.form['username']
        password = request.form['password']
        if app_name and username and password:
            cur = mysql.connection.cursor()
            try:
                cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
                user_id = cur.fetchone()[0]
                cur.execute('INSERT INTO passwords (app_name, username, password, user_id) VALUES (%s, %s, %s, %s)',
                            (app_name, username, password, user_id))
                mysql.connection.commit()
                flash("Password saved successfully!", "success")
                return redirect(url_for('dashboard'))
            except Exception as e:
                flash(f"Error: {e}", "error")
            finally:
                cur.close()
        else:
            flash("Please fill out all fields.", "error")
    return render_template('add_password.html')

@app.route('/view_passwords')
def view_passwords():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
    user_id = cur.fetchone()[0]
    cur.execute('SELECT id, app_name, username, password FROM passwords WHERE user_id = %s', (user_id,))
    passwords = cur.fetchall()
    cur.close()

    return render_template('view_passwords.html', passwords=passwords)

@app.route('/delete_password/<int:password_id>', methods=['POST'])
def delete_password(password_id):
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT app_name FROM passwords WHERE id = %s', (password_id,))
    app_name = cur.fetchone()[0]  # Fetch the application name to use in flash message
    cur.close()

    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM passwords WHERE id = %s', (password_id,))
    mysql.connection.commit()
    cur.close()
    flash("Password for '{}' deleted successfully!".format(app_name), "success")
    return redirect(url_for('view_passwords'))

@app.route('/upload_document', methods=['GET', 'POST'])
def upload_document():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        document = request.files['document']
        document_name = request.form['doc_name']
        if document and document_name:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], document.filename)
            document.save(filename)

            cur = mysql.connection.cursor()
            try:
                cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
                user_id = cur.fetchone()[0]
                cur.execute('INSERT INTO documents (document_name, document_path, user_id) VALUES (%s, %s, %s)',
                            (document_name, filename, user_id))
                mysql.connection.commit()
                flash("Document uploaded successfully!", "success")
                return redirect(url_for('view_documents'))
            except Exception as e:
                flash(f"Error: {e}", "error")
            finally:
                cur.close()
        else:
            flash("Please fill out all fields.", "error")
    return render_template('upload_document.html')

@app.route('/view_documents')
def view_documents():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
    user_id = cur.fetchone()[0]
    cur.execute('SELECT id, document_name FROM documents WHERE user_id = %s', (user_id,))
    documents = cur.fetchall()
    cur.close()

    return render_template('view_documents.html', documents=documents)

@app.route('/view_documents/<int:document_id>')
def view_document(document_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT document_name, document_path FROM documents WHERE id = %s', (document_id,))
    document = cur.fetchone()
    cur.close()

    if document:
        return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(document[1]))
    else:
        flash("Document not found.", "error")
        return redirect(url_for('view_documents'))

@app.route('/delete_document/<int:document_id>', methods=['POST'])
def delete_document(document_id):
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT document_path FROM documents WHERE id = %s', (document_id,))
    document_path = cur.fetchone()[0]
    cur.close()

    if document_path:
        try:
            os.remove(document_path)  # Delete the actual file from filesystem
        except OSError as e:
            flash(f"Error deleting document: {e}", "error")

    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM documents WHERE id = %s', (document_id,))
    mysql.connection.commit()
    cur.close()

    flash("Document deleted successfully!", "success")
    return redirect(url_for('view_documents'))

@app.route('/upload_photo', methods=['GET', 'POST'])
def upload_photo():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        photo = request.files['photo']
        photo_name = request.form['photo_name']
        if photo and photo_name:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
            photo.save(filename)

            cur = mysql.connection.cursor()
            try:
                cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
                user_id = cur.fetchone()[0]
                cur.execute('INSERT INTO photos (photo_name, photo_path, user_id) VALUES (%s, %s, %s)',
                            (photo_name, filename, user_id))
                mysql.connection.commit()
                flash("Photo uploaded successfully!", "success")
                return redirect(url_for('view_photos'))
            except Exception as e:
                flash(f"Error: {e}", "error")
            finally:
                cur.close()
        else:
            flash("Please fill out all fields.", "error")
    return render_template('upload_photo.html')

@app.route('/view_photos')
def view_photos():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
    user_id = cur.fetchone()[0]
    cur.execute('SELECT id, photo_name FROM photos WHERE user_id = %s', (user_id,))
    photos = cur.fetchall()
    cur.close()

    return render_template('view_photos.html', photos=photos)

@app.route('/view_photos/<int:photo_id>')
def view_photo(photo_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT photo_name, photo_path FROM photos WHERE id = %s', (photo_id,))
    photo = cur.fetchone()
    cur.close()

    if photo:
        return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(photo[1]), as_attachment=False)
    else:
        flash("Photo not found.", "error")
        return redirect(url_for('view_photos'))

@app.route('/delete_photo/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    try:
        # Fetch photo details to determine file path
        cur.execute('SELECT photo_path FROM photos WHERE id = %s AND user_id = (SELECT id FROM users WHERE username = %s)', (photo_id, session['username']))
        photo = cur.fetchone()

        if photo:
            # Delete the photo record from the database
            cur.execute('DELETE FROM photos WHERE id = %s', (photo_id,))
            mysql.connection.commit()

            # Remove the photo file from the server
            os.remove(photo[0])

            flash("Photo deleted successfully!", "success")
        else:
            flash("Photo not found or you don't have permission to delete it.", "error")

    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        cur.close()

    return redirect(url_for('view_photos'))

@app.route('/upload_video', methods=['GET', 'POST'])
def upload_video():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        video = request.files['video']
        video_name = request.form['video_name']
        if video and video_name:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
            video.save(filename)

            cur = mysql.connection.cursor()
            try:
                cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
                user_id = cur.fetchone()[0]
                cur.execute('INSERT INTO videos (video_name, video_path, user_id) VALUES (%s, %s, %s)',
                            (video_name, filename, user_id))
                mysql.connection.commit()
                flash("Video uploaded successfully!", "success")
                return redirect(url_for('view_videos'))
            except Exception as e:
                flash(f"Error: {e}", "error")
            finally:
                cur.close()
        else:
            flash("Please fill out all fields.", "error")
    return render_template('upload_video.html')

@app.route('/view_videos')
def view_videos():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
    user_id = cur.fetchone()[0]
    cur.execute('SELECT id, video_name FROM videos WHERE user_id = %s', (user_id,))
    videos = cur.fetchall()
    cur.close()

    return render_template('view_videos.html', videos=videos)

@app.route('/view_videos/<int:video_id>')
def view_video(video_id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT video_name, video_path FROM videos WHERE id = %s', (video_id,))
    video = cur.fetchone()
    cur.close()

    if video:
        return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(video[1]), as_attachment=False)
    else:
        flash("Video not found.", "error")
        return redirect(url_for('view_videos'))

@app.route('/delete_video/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    try:
        # Check if the video belongs to the logged-in user
        cur.execute('SELECT video_path FROM videos WHERE id = %s AND user_id = (SELECT id FROM users WHERE username = %s)', (video_id, session['username']))
        video = cur.fetchone()

        if video:
            # Delete the video record from the database
            cur.execute('DELETE FROM videos WHERE id = %s', (video_id,))
            mysql.connection.commit()

            # Remove the video file from the filesystem
            os.remove(video[0])

            flash("Video deleted successfully!", "success")
        else:
            flash("Video not found or not authorized.", "error")
    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        cur.close()

    return redirect(url_for('view_videos'))

@app.route('/add_api_key', methods=['GET', 'POST'])
def add_api_key():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        service_name = request.form.get('service_name')
        api_key = request.form.get('api_key')
        if service_name and api_key:
            cur = mysql.connection.cursor()
            try:
                cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
                user_id = cur.fetchone()[0]
                cur.execute('INSERT INTO api_keys (service_name, api_key, user_id) VALUES (%s, %s, %s)',
                            (service_name, api_key, user_id))
                mysql.connection.commit()
                flash("API key saved successfully!", "success")
                return redirect(url_for('dashboard'))
            except Exception as e:
                flash(f"Error: {e}", "error")
            finally:
                cur.close()
        else:
            flash("Please fill out all fields.", "error")
    return render_template('add_api_key.html')

@app.route('/view_api_keys')
def view_api_keys():
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT id FROM users WHERE username = %s', (session['username'],))
    user_id = cur.fetchone()[0]
    cur.execute('SELECT id, service_name, api_key FROM api_keys WHERE user_id = %s', (user_id,))
    api_keys = cur.fetchall()
    cur.close()

    # Convert the tuple data to a list of dictionaries for easier template rendering
    api_keys_list = [{'id': key[0], 'service_name': key[1], 'api_key': key[2]} for key in api_keys]

    return render_template('view_api_keys.html', api_keys=api_keys_list)

@app.route('/delete_api_key/<int:api_key_id>', methods=['POST'])
def delete_api_key(api_key_id):
    if 'username' not in session:
        flash("You need to login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute('SELECT service_name FROM api_keys WHERE id = %s', (api_key_id,))
    service_name = cur.fetchone()[0]  # Fetch the service name to use in flash message
    cur.close()

    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM api_keys WHERE id = %s', (api_key_id,))
    mysql.connection.commit()
    cur.close()
    flash("API key for '{}' deleted successfully!".format(service_name), "success")
    return redirect(url_for('view_api_keys'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

app.run(host="0.0.0.0", port=5000, debug=True)
