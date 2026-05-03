import sqlite3
import os
from datetime import date, datetime
from flask import Flask, render_template, request, url_for, redirect, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'anton_secret_777')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}
MONTH_NAMES_SHORT = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']

ROLE_LABELS = {
    'admin':   '👑 Админ',
    'teacher': '👩‍🏫 Кл. рук.',
    'parent':  '👨‍👩‍👦 Родитель',
    'student': '🎒 Ученик',
}

# Права по ролям
ROLE_PERMS = {
    'admin':   ['view','post','photo','material','student','birthday','manage_users'],
    'teacher': ['view','post','photo','material','student','birthday'],
    'parent':  ['view'],
    'student': ['view'],
}

def can(action):
    role = session.get('role', '')
    return action in ROLE_PERMS.get(role, [])

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        title TEXT NOT NULL, content TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, url TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, role TEXT, emoji TEXT DEFAULT "🧑")''')
    conn.execute('''CREATE TABLE IF NOT EXISTS birthdays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, birthdate TEXT NOT NULL, emoji TEXT DEFAULT "🎂")''')
    # Таблица users — создаём если нет
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT "student",
        display_name TEXT)''')

    # Гарантируем что админ всегда существует
    admin = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not admin:
        conn.execute("INSERT INTO users (username, password, role, display_name) VALUES (?,?,?,?)",
                     ('admin', 'admin123', 'admin', 'Администратор'))

    # Гарантируем что учитель всегда существует
    teacher = conn.execute("SELECT id FROM users WHERE username='teacher'").fetchone()
    if not teacher:
        conn.execute("INSERT INTO users (username, password, role, display_name) VALUES (?,?,?,?)",
                     ('teacher', 'teacher123', 'teacher', 'Классный руководитель'))

    conn.commit()
    conn.close()

init_db()

def days_until_birthday(birthdate_str):
    try:
        bd = datetime.strptime(birthdate_str, '%Y-%m-%d').date()
    except ValueError:
        return 999, False, birthdate_str
    today = date.today()
    next_bd = bd.replace(year=today.year)
    if next_bd < today:
        next_bd = next_bd.replace(year=today.year + 1)
    days_left = (next_bd - today).days
    is_today = (days_left == 0)
    date_str = f"{bd.day} {MONTH_NAMES_SHORT[bd.month - 1]}"
    return days_left, is_today, date_str

# ─── AUTH ─────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?", (username, password)
        ).fetchone()
        conn.close()
        if user:
            session.permanent = True
            session['user'] = user['username']
            session['role'] = user['role']
            session['display_name'] = user['display_name'] or user['username']
            return redirect(url_for('index'))
        error = "Неверный логин или пароль"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── ГЛАВНАЯ ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM posts ORDER BY created DESC').fetchall()
    bdays_raw = conn.execute('SELECT * FROM birthdays').fetchall()
    conn.close()
    bdays = []
    for b in bdays_raw:
        days_left, is_today, date_str = days_until_birthday(b['birthdate'])
        bdays.append({'name': b['name'], 'emoji': b['emoji'],
                      'days_left': days_left, 'is_today': is_today, 'date_str': date_str})
    bdays.sort(key=lambda x: x['days_left'])
    return render_template('index.html',
        user=session['display_name'], role=session['role'],
        role_label=ROLE_LABELS.get(session['role'], ''),
        can=can, posts=posts, birthdays=bdays[:5])

# ─── ОБЪЯВЛЕНИЯ ───────────────────────────────────────────────────────────────

@app.route('/create', methods=['GET', 'POST'])
def create():
    if not can('post'): return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
                     (request.form['title'], request.form['content']))
        conn.commit(); conn.close()
        return redirect(url_for('index'))
    return render_template('create.html', user=session['display_name'], role=session['role'], can=can)

# ─── ГАЛЕРЕЯ ──────────────────────────────────────────────────────────────────

@app.route('/gallery')
def gallery():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    photos = conn.execute('SELECT * FROM photos').fetchall()
    conn.close()
    return render_template('gallery.html', user=session['display_name'], role=session['role'], can=can, photos=photos)

@app.route('/add_photo', methods=['GET', 'POST'])
def add_photo():
    if not can('photo'): return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO photos (title, url) VALUES (?, ?)',
                     (request.form['title'], request.form['url']))
        conn.commit(); conn.close()
        return redirect(url_for('gallery'))
    return render_template('add_photo.html', user=session['display_name'], role=session['role'], can=can)

# ─── БАЗА ЗНАНИЙ ──────────────────────────────────────────────────────────────

@app.route('/knowledge')
def knowledge():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    materials = conn.execute('SELECT * FROM knowledge').fetchall()
    conn.close()
    return render_template('knowledge.html', user=session['display_name'], role=session['role'], can=can, materials=materials)

@app.route('/add_material', methods=['GET', 'POST'])
def add_material():
    if not can('material'): return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO knowledge (category, title, url) VALUES (?, ?, ?)',
                     (request.form['category'], request.form['title'], request.form['url']))
        conn.commit(); conn.close()
        return redirect(url_for('knowledge'))
    return render_template('add_material.html', user=session['display_name'], role=session['role'], can=can)

# ─── УЧЕНИКИ ──────────────────────────────────────────────────────────────────

@app.route('/students')
def students():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    students_list = conn.execute('SELECT * FROM students ORDER BY name').fetchall()
    conn.close()
    return render_template('students.html', user=session['display_name'], role=session['role'], can=can, students=students_list)

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if not can('student'): return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO students (name, role, emoji) VALUES (?, ?, ?)',
                     (request.form['name'], request.form.get('role') or None, request.form.get('emoji','🧑')))
        conn.commit(); conn.close()
        return redirect(url_for('students'))
    return render_template('add_student.html', user=session['display_name'], role=session['role'], can=can)

# ─── ДНИ РОЖДЕНИЯ ─────────────────────────────────────────────────────────────

@app.route('/birthdays')
def birthdays():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    bdays_raw = conn.execute('SELECT * FROM birthdays').fetchall()
    conn.close()
    todays, all_bdays = [], []
    for b in bdays_raw:
        days_left, is_today, date_str = days_until_birthday(b['birthdate'])
        entry = {'name': b['name'], 'emoji': b['emoji'], 'days_left': days_left,
                 'is_today': is_today, 'date_str': date_str,
                 'month': datetime.strptime(b['birthdate'], '%Y-%m-%d').month}
        all_bdays.append(entry)
        if is_today: todays.append(entry)
    all_bdays.sort(key=lambda x: x['days_left'])
    bdays_by_month = {}
    for b in all_bdays:
        m = MONTHS_RU[b['month']]
        if m not in bdays_by_month: bdays_by_month[m] = []
        bdays_by_month[m].append(b)
    return render_template('birthdays.html',
        user=session['display_name'], role=session['role'], can=can,
        todays=todays, birthdays_by_month=bdays_by_month)

@app.route('/add_birthday', methods=['GET', 'POST'])
def add_birthday():
    if not can('birthday'): return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO birthdays (name, birthdate, emoji) VALUES (?, ?, ?)',
                     (request.form['name'], request.form['birthdate'], request.form.get('emoji','🎂')))
        conn.commit(); conn.close()
        return redirect(url_for('birthdays'))
    return render_template('add_birthday.html', user=session['display_name'], role=session['role'], can=can)

# ─── УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ────────────────────────────────────────────────

@app.route('/users')
def users():
    if not can('manage_users'): return "Доступ запрещён", 403
    conn = get_db_connection()
    all_users = conn.execute('SELECT * FROM users ORDER BY role, username').fetchall()
    conn.close()
    return render_template('users.html',
        user=session['display_name'], role=session['role'], can=can,
        all_users=all_users, role_labels=ROLE_LABELS)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if not can('manage_users'): return "Доступ запрещён", 403
    error = None
    if request.method == 'POST':
        username     = request.form['username'].strip()
        password     = request.form['password']
        role         = request.form['role']
        display_name = request.form.get('display_name', '').strip() or username
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO users (username, password, role, display_name) VALUES (?,?,?,?)',
                         (username, password, role, display_name))
            conn.commit(); conn.close()
            return redirect(url_for('users'))
        except sqlite3.IntegrityError:
            error = f'Логин «{username}» уже занят, выбери другой'
    return render_template('add_user.html',
        user=session['display_name'], role=session['role'], can=can,
        error=error, role_labels=ROLE_LABELS)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not can('manage_users'): return "Доступ запрещён", 403
    conn = get_db_connection()
    target = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if target and target['username'] != 'admin':
        conn.execute('DELETE FROM users WHERE id=?', (user_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('users'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
