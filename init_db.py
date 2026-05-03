import sqlite3

connection = sqlite3.connect('database.db')

with open('schema.sql') as f:
    connection.executescript(f.read())

cur = connection.cursor()

# Добавим первое тестовое объявление
cur.execute("INSERT INTO posts (title, content) VALUES (?, ?)",
            ('Добро пожаловать!', 'Это первое объявление в нашей базе данных.')
            )

connection.commit()
connection.close()
print("База данных успешно создана!")