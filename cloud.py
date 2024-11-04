from flask import *
import sqlite3
import os
import subprocess


app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'storage_system.db'

@app.before_request
def redirect_http_to_https():
    if not request.is_secure:
        print('Not secure')
        return redirect(request.url.replace("https://", "http://"))
    else:
        print('Is secure')

# Initialize database
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            storage_used INTEGER DEFAULT 0,
            storage_limit INTEGER DEFAULT 1073741824,
            subscription_active INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            os.makedirs(os.path.join('user_storage', username))
            flash('User registered successfully!', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists!', 'error')
        finally:
            conn.close()
    return render_template('register.html')


# Admin username and password (could be stored in a database or config file)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"  # Securely store this in a real app

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Admin login check
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['username'] = username
            session['is_admin'] = True
            flash('Logged in as admin!', 'success')
            return redirect(url_for('admin_dashboard'))

        # Normal user login
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['username'] = username
            session['is_admin'] = False
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


# Get list of uploaded files for the current user along with file sizes
def get_user_files(username):
    user_dir = os.path.join('user_storage', username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    files = os.listdir(user_dir)

    # Create a list of files with their sizes
    file_info = []
    for file in files:
        file_path = os.path.join(user_dir, file)
        if os.path.isfile(file_path):
            file_size = round(os.path.getsize(file_path) / (1024 * 1024), 2)  # Size in MB
            file_info.append((file, file_size))  # Each item is a tuple: (file name, size in MB)

    return file_info


# Convert bytes to megabytes
def bytes_to_mb(bytes):
    return round(bytes / (1024 * 1024), 2)


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        flash('Please log in first!', 'error')
        return redirect(url_for('login'))

    username = session['username']

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT storage_used, storage_limit, subscription_active FROM users WHERE username=?', (username,))
    user_data = cursor.fetchone()
    conn.close()

    # Convert storage data to megabytes
    storage_used_mb = bytes_to_mb(user_data[0])
    storage_limit_mb = bytes_to_mb(user_data[1])
    free_space_mb = storage_limit_mb - storage_used_mb

    if request.method == 'POST':
        # Handle multiple file uploads
        files = request.files.getlist('file')
        total_file_size = 0

        for file in files:
            file.seek(0, os.SEEK_END)  # Move pointer to the end to calculate file size
            file_size = file.tell()  # Get file size in bytes
            file.seek(0)  # Reset file pointer for saving

            total_file_size += file_size

        # Check if adding the new files will exceed the storage limit
        if user_data[0] + total_file_size > user_data[1]:
            flash('Storage limit exceeded!', 'error')
        else:
            for file in files:
                file_size = file.tell()  # Get the file size again (or store earlier)
                file.seek(0)  # Reset file pointer for saving
                filepath = os.path.join('user_storage', username, file.filename)
                file.save(filepath)  # Save the file

                # Update the database with the new storage used
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET storage_used = storage_used + ? WHERE username = ?',
                               (file_size, username))
                conn.commit()
                conn.close()

            flash('Files uploaded successfully!', 'success')

    # Get the user's files for the download section
    user_files = get_user_files(username)

    return render_template('dashboard.html', storage_used_mb=storage_used_mb, storage_limit_mb=storage_limit_mb,
                           free_space_mb=free_space_mb, subscription_active=user_data[2], user_files=user_files)


# Function to serve text-based file content for editing
@app.route('/edit_file/<filename>', methods=['GET', 'POST'])
def edit_file(filename):
    username = session.get('username')
    user_dir = os.path.join('user_storage', username)
    file_path = os.path.join(user_dir, filename)

    if request.method == 'POST':
        # Save edited file
        new_content = request.form.get('file_content', '')
        if new_content:  # Check if there is content to save
            with open(file_path, 'w') as file:
                file.write(new_content)
            flash(f'File "{filename}" saved successfully!', 'success')
        else:
            flash('No content to save!', 'error')
        return redirect(url_for('edit_file', filename=filename))

    # Display file contents in a text editor
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            file_content = file.read()
        return render_template('edit_file.html', filename=filename, file_content=file_content)

    flash('File not found!', 'error')
    return redirect(url_for('dashboard'))


@app.route('/run_python', methods=['POST'])
def run_python():
    code = request.json.get('code')

    try:
        # Use subprocess to run the Python code safely
        result = subprocess.run(
            ['python3', '-c', code],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout if result.stdout else result.stderr
    except subprocess.CalledProcessError as e:
        output = e.stderr

    return jsonify({"output": output})


# Serve media files
@app.route('/media/<filename>')
def media_file(filename):
    username = session['username']
    file_path = os.path.join('user_storage', username, filename)
    return send_file(file_path)

# Admin
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'is_admin' not in session:
        print(session)
        flash('Admin access required!', 'error')
        return redirect(url_for('login_admin'))

    if request.method == 'POST':
        action = request.form['action']
        username = request.form['username']
        if action == 'add_subscription':
            extra_storage = int(request.form['extra_storage'])  # Additional storage in bytes
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET storage_limit = storage_limit + ?, subscription_active = 1 WHERE username = ?',
                (extra_storage, username))
            conn.commit()
            conn.close()
            flash('Subscription added!', 'success')
        elif action == 'revoke_subscription':
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET storage_limit = 3221225472, subscription_active = 0 WHERE username = ?',
                           (username,))
            conn.commit()
            conn.close()
            flash('Subscription revoked!', 'success')

    return render_template('admin.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'username' not in session or not session.get('is_admin'):
        flash('Admin access required!', 'error')
        return redirect(url_for('login'))
    return render_template('admin.html')


# Get list of uploaded files for the current user along with file sizes
def get_user_files_with_sizes(username):
    user_dir = os.path.join('user_storage', username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    files = os.listdir(user_dir)

    # Create a list of files with their sizes
    file_info = []
    for file in files:
        file_path = os.path.join(user_dir, file)
        if os.path.isfile(file_path):
            file_size = round(os.path.getsize(file_path) / (1024 * 1024), 2)  # Size in MB
            file_info.append((file, file_size))  # Tuple with file name and size
    return file_info


# Handle file deletion
@app.route('/delete_file/<filename>', methods=['POST'])
def delete_file(filename):
    if 'username' not in session:
        flash('Please log in first!', 'error')
        return redirect(url_for('login'))

    username = session['username']
    user_dir = os.path.join('user_storage', username)
    file_path = os.path.join(user_dir, filename)

    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)  # Size of the file in bytes
        os.remove(file_path)
        # Deduct the size from user's storage in the database
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET storage_used = storage_used - ? WHERE username = ?', (file_size, username))
        conn.commit()
        conn.close()
        flash(f'File "{filename}" deleted successfully!', 'success')
    else:
        flash(f'File "{filename}" not found!', 'error')

    return redirect(url_for('dashboard'))


# Admin login
@app.route('/admin_login', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin':
            session['admin'] = True
            flash('Admin logged in!', 'success')
            return redirect(url_for('admin'))
        else:
            print(f'{username},{password}')
            flash('Invalid admin credentials!', 'error')
    return render_template('login.html')


# Route to download files
@app.route('/download/<filename>')
def download_file(filename):
    if 'username' not in session:
        flash('Please log in first!', 'error')
        return redirect(url_for('login'))

    username = session['username']
    user_dir = os.path.join('user_storage', username)
    file_path = os.path.join(user_dir, filename)

    if os.path.exists(file_path):
        return send_from_directory(user_dir, filename, as_attachment=True)
    else:
        flash('File not found!', 'error')
        return redirect(url_for('dashboard'))



# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out!', 'success')
    return redirect(url_for('login'))

@app.route('/request_upgrade', methods=['GET', 'POST'])
def request_upgrade():
    if 'username' not in session:
        flash('Please log in first!', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        contact_method = request.form['contact_method']
        contact_info = request.form['contact_info']
        storage_amount = request.form['storage_amount']

        with open('C:\\Users\\idapu\\Documents\\Code\\Python\\CloudCache\\user_storage\\admin\\requests.txt', 'a') as f:
            f.write(f'Name: {name}, Username: {session['username']}, {contact_method}: {contact_info}, Amount: {storage_amount}GB\n')

        flash('Upgrade request submitted successfully! An admin will review it soon.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('request_upgrade.html')

if __name__ == '__main__':
    # init_db()
    cert_file = "cert.pem"  # Path to your certificate
    key_file = 'key_without_passphrase.pem'  # Path to your private key
    # app.run(debug=True, port=5001, host='0.0.0.0')
    app.run(debug=False, port=5002, host="0.0.0.0", ssl_context=(cert_file, key_file))
