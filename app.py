import sqlite3
import os
from datetime import date, datetime
from flask import Flask, render_template, request, url_for, redirect, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'anton_secret_777')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

USERS = {
    "admin": "12345",
    "student": "class2026",
    "teacher": "math_is_cool"
}

# ─── Названия месяцев ─────────────────────────────────────────────────────────
MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}

DAY_NAMES_RU = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']

MONTH_NAMES_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн',
                     'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

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
    conn.commit()
    conn.close()

init_db()

# ─── Хелпер: считаем дни до следующего дня рождения ──────────────────────────
def days_until_birthday(birthdate_str):
    """Возвращает (days_left, is_today, date_str)"""
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

# ─── СТАРЫЕ МАРШРУТЫ (не изменены) ───────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
        if USERS.get(username) == password:
            session.permanent = True
            session['user'] = username
            return redirect(url_for('index'))
        return "Ошибка! <a href='/login'>Назад</a>"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/create', methods=['GET', 'POST'])
def create():
    if session.get('user') != 'admin': return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
                     (request.form['title'], request.form['content']))
        conn.commit(); conn.close()
        return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/add_photo', methods=['GET', 'POST'])
def add_photo():
    if session.get('user') != 'admin': return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO photos (title, url) VALUES (?, ?)',
                     (request.form['title'], request.form['url']))
        conn.commit(); conn.close()
        return redirect(url_for('gallery'))
    return render_template('add_photo.html')

@app.route('/add_material', methods=['GET', 'POST'])
def add_material():
    if session.get('user') != 'admin': return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO knowledge (category, title, url) VALUES (?, ?, ?)',
                     (request.form['category'], request.form['title'], request.form['url']))
        conn.commit(); conn.close()
        return redirect(url_for('knowledge'))
    return render_template('add_material.html')

# ─── ОБНОВЛЁННЫЕ МАРШРУТЫ ─────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM posts ORDER BY created DESC').fetchall()
    bdays_raw = conn.execute('SELECT * FROM birthdays').fetchall()
    conn.close()

    # Ближайшие 5 дней рождений для главной страницы
    bdays = []
    for b in bdays_raw:
        days_left, is_today, date_str = days_until_birthday(b['birthdate'])
        bdays.append({
            'name': b['name'], 'emoji': b['emoji'],
            'days_left': days_left, 'is_today': is_today, 'date_str': date_str
        })
    bdays.sort(key=lambda x: x['days_left'])
    bdays = bdays[:5]

    return render_template('index.html', user=session['user'], posts=posts, birthdays=bdays)

@app.route('/gallery')
def gallery():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    photos = conn.execute('SELECT * FROM photos').fetchall()
    conn.close()
    return render_template('gallery.html', user=session['user'], photos=photos)

@app.route('/knowledge')
def knowledge():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    materials = conn.execute('SELECT * FROM knowledge').fetchall()
    conn.close()
    return render_template('knowledge.html', user=session['user'], materials=materials)

# ─── НОВЫЕ МАРШРУТЫ ───────────────────────────────────────────────────────────

@app.route('/students')
def students():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    students_list = conn.execute('SELECT * FROM students ORDER BY name').fetchall()
    conn.close()
    return render_template('students.html', user=session['user'], students=students_list)

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if session.get('user') != 'admin': return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO students (name, role, emoji) VALUES (?, ?, ?)',
                     (request.form['name'],
                      request.form.get('role', '') or None,
                      request.form.get('emoji', '🧑')))
        conn.commit(); conn.close()
        return redirect(url_for('students'))
    return render_template('add_student.html', user=session['user'])

@app.route('/birthdays')
def birthdays():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    bdays_raw = conn.execute('SELECT * FROM birthdays').fetchall()
    conn.close()

    todays = []
    all_bdays = []

    for b in bdays_raw:
        days_left, is_today, date_str = days_until_birthday(b['birthdate'])
        entry = {
            'name': b['name'], 'emoji': b['emoji'],
            'days_left': days_left, 'is_today': is_today, 'date_str': date_str,
            'month': datetime.strptime(b['birthdate'], '%Y-%m-%d').month
        }
        all_bdays.append(entry)
        if is_today:
            todays.append(entry)

    # Группируем по месяцу, сортируем по дням до дня рождения
    all_bdays.sort(key=lambda x: x['days_left'])
    birthdays_by_month = {}
    for b in all_bdays:
        month_name = MONTHS_RU[b['month']]
        if month_name not in birthdays_by_month:
            birthdays_by_month[month_name] = []
        birthdays_by_month[month_name].append(b)

    return render_template('birthdays.html',
                           user=session['user'],
                           todays=todays,
                           birthdays_by_month=birthdays_by_month)

@app.route('/add_birthday', methods=['GET', 'POST'])
def add_birthday():
    if session.get('user') != 'admin': return "Доступ запрещён", 403
    if request.method == 'POST':
        conn = get_db_connection()
        conn.execute('INSERT INTO birthdays (name, birthdate, emoji) VALUES (?, ?, ?)',
                     (request.form['name'],
                      request.form['birthdate'],
                      request.form.get('emoji', '🎂')))
        conn.commit(); conn.close()
        return redirect(url_for('birthdays'))
    return render_template('add_birthday.html', user=session['user'])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
