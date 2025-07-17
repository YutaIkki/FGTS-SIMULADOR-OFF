import sqlite3

def init_db():
    conn = sqlite3.connect("consultas.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf TEXT,
            data TEXT,
            resultado TEXT
        )
    """)
    conn.commit()
    conn.close()
