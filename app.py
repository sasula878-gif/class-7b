import sqlite3
import os
from datetime import date, datetime
from flask import Flask, render_template, request, url_for, redirect, session

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'class7b_secret_key_2024')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
    5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
    9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}
MONTH_SHORT = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']

DAYS_RU = {1:'Понедельник', 2:'Вторник', 3:'Среда', 4:'Четверг', 5:'Пятница'}
DAYS_SHORT = {1:'Пн', 2:'Вт', 3:'Ср', 4:'Чт', 5:'Пт'}

ROLE_LABELS = {
    'admin':   '👑 Админ',
    'teacher': '👩‍🏫 Кл. рук.',
    'parent':  '👨‍👩‍👦 Родитель',
    'student': '🎒 Ученик',
}

ROLE_PERMS = {
    'admin':   ['view','post','photo','material','student','birthday','manage_users','schedule'],
    'teacher': ['view','post','photo','material','student','birthday','schedule'],
    'parent':  ['view'],
    'student': ['view'],
}

def can(action):
    return action in ROLE_PERMS.get(session.get('role',''), [])

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT "student",
        display_name TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        title TEXT NOT NULL,
        content TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        url TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT,
        emoji TEXT NOT NULL DEFAULT "🧑")''')
    conn.execute('''CREATE TABLE IF NOT EXISTS birthdays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        birthdate TEXT NOT NULL,
        emoji TEXT NOT NULL DEFAULT "🎂")''')
    conn.execute('''CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_num INTEGER NOT NULL,
        lesson_num INTEGER NOT NULL,
        subject TEXT NOT NULL,
        teacher TEXT DEFAULT "",
        time_start TEXT NOT NULL,
        time_end TEXT NOT NULL)''')
    if not conn.execute("SELECT 1 FROM schedule").fetchone():
        default = [
            (1,1,"Математика","","08:00","08:45"),(1,2,"Русский язык","","08:55","09:40"),
            (1,3,"История","","09:55","10:40"),(1,4,"Биология","","10:50","11:35"),
            (1,5,"Физкультура","","11:50","12:35"),(1,6,"Литература","","12:45","13:30"),
            (2,1,"Английский язык","","08:00","08:45"),(2,2,"Математика","","08:55","09:40"),
            (2,3,"Физика","","09:55","10:40"),(2,4,"Русский язык","","10:50","11:35"),
            (2,5,"Информатика","","11:50","12:35"),
            (3,1,"История","","08:00","08:45"),(3,2,"Биология","","08:55","09:40"),
            (3,3,"Математика","","09:55","10:40"),(3,4,"Английский язык","","10:50","11:35"),
            (3,5,"Физкультура","","11:50","12:35"),(3,6,"Литература","","12:45","13:30"),
            (4,1,"Русский язык","","08:00","08:45"),(4,2,"Физика","","08:55","09:40"),
            (4,3,"Английский язык","","09:55","10:40"),(4,4,"Математика","","10:50","11:35"),
            (4,5,"Химия","","11:50","12:35"),
            (5,1,"Литература","","08:00","08:45"),(5,2,"Математика","","08:55","09:40"),
            (5,3,"Русский язык","","09:55","10:40"),(5,4,"История","","10:50","11:35"),
            (5,5,"Биология","","11:50","12:35"),(5,6,"Информатика","","12:45","13:30"),
        ]
        conn.executemany("INSERT INTO schedule (day_num,lesson_num,subject,teacher,time_start,time_end) VALUES (?,?,?,?,?,?)", default)
    # Всегда проверяем наличие дефолтного админа
    if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        conn.execute("INSERT INTO users (username,password,role,display_name) VALUES (?,?,?,?)",
                     ('admin','admin123','admin','Администратор'))
    if not conn.execute("SELECT 1 FROM users WHERE username='teacher'").fetchone():
        conn.execute("INSERT INTO users (username,password,role,display_name) VALUES (?,?,?,?)",
                     ('teacher','teacher123','teacher','Классный руководитель'))
    conn.commit()
    conn.close()

init_db()

def bday_info(birthdate_str):
    try:
        bd = datetime.strptime(birthdate_str, '%Y-%m-%d').date()
    except:
        return 999, False, '?'
    today = date.today()
    nb = bd.replace(year=today.year)
    if nb < today:
        nb = nb.replace(year=today.year + 1)
    days = (nb - today).days
    return days, days == 0, f"{bd.day} {MONTH_SHORT[bd.month-1]}"

# ── AUTH ──────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','')
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u,p)).fetchone()
        conn.close()
        if user:
            session['user']         = user['username']
            session['role']         = user['role']
            session['display_name'] = user['display_name']
            return redirect(url_for('index'))
        error = 'Неверный логин или пароль'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── ГЛАВНАЯ ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = get_db()
    posts = conn.execute('SELECT * FROM posts ORDER BY created DESC').fetchall()
    bdays_raw = conn.execute('SELECT * FROM birthdays').fetchall()
    today_num = datetime.now().isoweekday()
    schedule_today = conn.execute(
        'SELECT * FROM schedule WHERE day_num=? ORDER BY lesson_num',
        (today_num if today_num <= 5 else 1,)
    ).fetchall() if today_num <= 5 else []
    conn.close()
    bdays = sorted([
        {'name':b['name'],'emoji':b['emoji'],**dict(zip(['days_left','is_today','date_str'], bday_info(b['birthdate'])))}
        for b in bdays_raw
    ], key=lambda x: x['days_left'])[:5]
    return render_template('index.html',
        user=session['display_name'], role=session['role'],
        role_label=ROLE_LABELS.get(session['role'],''), can=can,
        posts=posts, birthdays=bdays,
        schedule_today=schedule_today,
        today_day_name=DAYS_RU.get(today_num,'Выходной'),
        today_num=today_num)

# ── ОБЪЯВЛЕНИЯ ────────────────────────────────────────────────────────────────

@app.route('/create', methods=['GET','POST'])
def create():
    if not can('post'): return redirect(url_for('index'))
    if request.method == 'POST':
        conn = get_db()
        conn.execute('INSERT INTO posts (title,content) VALUES (?,?)',
                     (request.form['title'], request.form['content']))
        conn.commit(); conn.close()
        return redirect(url_for('index'))
    return render_template('create.html',
        user=session['display_name'], role=session['role'], can=can)

# ── ГАЛЕРЕЯ ───────────────────────────────────────────────────────────────────

@app.route('/gallery')
def gallery():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db()
    photos = conn.execute('SELECT * FROM photos').fetchall()
    conn.close()
    return render_template('gallery.html',
        user=session['display_name'], role=session['role'], can=can, photos=photos)

@app.route('/add_photo', methods=['GET','POST'])
def add_photo():
    if not can('photo'): return redirect(url_for('gallery'))
    if request.method == 'POST':
        conn = get_db()
        conn.execute('INSERT INTO photos (title,url) VALUES (?,?)',
                     (request.form['title'], request.form['url']))
        conn.commit(); conn.close()
        return redirect(url_for('gallery'))
    return render_template('add_photo.html',
        user=session['display_name'], role=session['role'], can=can)

# ── БАЗА ЗНАНИЙ ───────────────────────────────────────────────────────────────

@app.route('/knowledge')
def knowledge():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db()
    materials = conn.execute('SELECT * FROM knowledge').fetchall()
    conn.close()
    return render_template('knowledge.html',
        user=session['display_name'], role=session['role'], can=can, materials=materials)

@app.route('/add_material', methods=['GET','POST'])
def add_material():
    if not can('material'): return redirect(url_for('knowledge'))
    if request.method == 'POST':
        conn = get_db()
        conn.execute('INSERT INTO knowledge (category,title,url) VALUES (?,?,?)',
                     (request.form['category'], request.form['title'], request.form['url']))
        conn.commit(); conn.close()
        return redirect(url_for('knowledge'))
    return render_template('add_material.html',
        user=session['display_name'], role=session['role'], can=can)

# ── УЧЕНИКИ ───────────────────────────────────────────────────────────────────

@app.route('/students')
def students():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db()
    students_list = conn.execute('SELECT * FROM students ORDER BY name').fetchall()
    conn.close()
    return render_template('students.html',
        user=session['display_name'], role=session['role'], can=can, students=students_list)

@app.route('/add_student', methods=['GET','POST'])
def add_student():
    if not can('student'): return redirect(url_for('students'))
    if request.method == 'POST':
        conn = get_db()
        conn.execute('INSERT INTO students (name,role,emoji) VALUES (?,?,?)',
                     (request.form['name'],
                      request.form.get('role') or None,
                      request.form.get('emoji','🧑')))
        conn.commit(); conn.close()
        return redirect(url_for('students'))
    return render_template('add_student.html',
        user=session['display_name'], role=session['role'], can=can)

# ── ДНИ РОЖДЕНИЯ ──────────────────────────────────────────────────────────────

@app.route('/birthdays')
def birthdays():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db()
    bdays_raw = conn.execute('SELECT * FROM birthdays').fetchall()
    conn.close()
    todays, all_b = [], []
    for b in bdays_raw:
        dl, it, ds = bday_info(b['birthdate'])
        entry = {'name':b['name'],'emoji':b['emoji'],'days_left':dl,'is_today':it,
                 'date_str':ds,'month':datetime.strptime(b['birthdate'],'%Y-%m-%d').month}
        all_b.append(entry)
        if it: todays.append(entry)
    all_b.sort(key=lambda x: x['days_left'])
    by_month = {}
    for b in all_b:
        m = MONTHS_RU[b['month']]
        by_month.setdefault(m, []).append(b)
    return render_template('birthdays.html',
        user=session['display_name'], role=session['role'], can=can,
        todays=todays, birthdays_by_month=by_month)

@app.route('/add_birthday', methods=['GET','POST'])
def add_birthday():
    if not can('birthday'): return redirect(url_for('birthdays'))
    if request.method == 'POST':
        conn = get_db()
        conn.execute('INSERT INTO birthdays (name,birthdate,emoji) VALUES (?,?,?)',
                     (request.form['name'], request.form['birthdate'], request.form.get('emoji','🎂')))
        conn.commit(); conn.close()
        return redirect(url_for('birthdays'))
    return render_template('add_birthday.html',
        user=session['display_name'], role=session['role'], can=can)

# ── ПОЛЬЗОВАТЕЛИ ──────────────────────────────────────────────────────────────

@app.route('/users')
def users():
    if not can('manage_users'): return redirect(url_for('index'))
    conn = get_db()
    all_users = conn.execute('SELECT * FROM users ORDER BY role, display_name').fetchall()
    conn.close()
    return render_template('users.html',
        user=session['display_name'], role=session['role'], can=can,
        all_users=all_users, role_labels=ROLE_LABELS)

@app.route('/add_user', methods=['GET','POST'])
def add_user():
    if not can('manage_users'): return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        uname  = request.form['username'].strip()
        pwd    = request.form['password'].strip()
        role   = request.form['role']
        dname  = request.form.get('display_name','').strip() or uname
        try:
            conn = get_db()
            conn.execute('INSERT INTO users (username,password,role,display_name) VALUES (?,?,?,?)',
                         (uname, pwd, role, dname))
            conn.commit(); conn.close()
            return redirect(url_for('users'))
        except sqlite3.IntegrityError:
            error = f'Логин «{uname}» уже занят — выбери другой'
    return render_template('add_user.html',
        user=session['display_name'], role=session['role'], can=can,
        error=error, role_labels=ROLE_LABELS)

@app.route('/delete_user/<int:uid>', methods=['POST'])
def delete_user(uid):
    if not can('manage_users'): return redirect(url_for('index'))
    conn = get_db()
    target = conn.execute('SELECT username FROM users WHERE id=?', (uid,)).fetchone()
    if target and target['username'] != 'admin':
        conn.execute('DELETE FROM users WHERE id=?', (uid,))
        conn.commit()
    conn.close()
    return redirect(url_for('users'))


# ── РАСПИСАНИЕ ────────────────────────────────────────────────────────────────

@app.route('/schedule')
def schedule():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db()
    rows = conn.execute('SELECT * FROM schedule ORDER BY day_num, lesson_num').fetchall()
    conn.close()
    # Группируем по дням
    days = {}
    for r in rows:
        d = r['day_num']
        if d not in days: days[d] = []
        days[d].append(r)
    today_num = datetime.now().isoweekday()  # 1=пн ... 7=вс
    return render_template('schedule.html',
        user=session['display_name'], role=session['role'], can=can,
        days=days, days_ru=DAYS_RU, days_short=DAYS_SHORT, today_num=today_num)

@app.route('/schedule/edit/<int:day>', methods=['GET','POST'])
def schedule_edit(day):
    if not can('schedule'): return redirect(url_for('schedule'))
    conn = get_db()
    if request.method == 'POST':
        # Удаляем старые уроки этого дня
        conn.execute('DELETE FROM schedule WHERE day_num=?', (day,))
        # Вставляем новые
        subjects  = request.form.getlist('subject')
        teachers  = request.form.getlist('teacher')
        t_starts  = request.form.getlist('time_start')
        t_ends    = request.form.getlist('time_end')
        for i, subj in enumerate(subjects):
            if subj.strip():
                conn.execute(
                    'INSERT INTO schedule (day_num,lesson_num,subject,teacher,time_start,time_end) VALUES (?,?,?,?,?,?)',
                    (day, i+1, subj.strip(), teachers[i].strip() if i < len(teachers) else '',
                     t_starts[i] if i < len(t_starts) else '08:00',
                     t_ends[i] if i < len(t_ends) else '08:45'))
        conn.commit(); conn.close()
        return redirect(url_for('schedule'))
    lessons = conn.execute('SELECT * FROM schedule WHERE day_num=? ORDER BY lesson_num', (day,)).fetchall()
    conn.close()
    return render_template('schedule_edit.html',
        user=session['display_name'], role=session['role'], can=can,
        day=day, day_name=DAYS_RU.get(day,'?'), lessons=lessons)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
