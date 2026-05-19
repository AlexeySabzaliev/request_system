import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import os

# ========== НАСТРОЙКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ ==========
# Если используется Render.com (переменная окружения DATABASE_URL)
if os.environ.get("DATABASE_URL"):
    DATABASE_URL = os.environ.get("DATABASE_URL")
    def get_db_connection():
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
# Для локального запуска на Windows
else:
    DB_CONFIG = {
        "dbname": "request_system",
        "user": "postgres",
        "password": "root",  # ← ИЗМЕНИТЕ НА ВАШ ПАРОЛЬ
        "host": "localhost",
        "port": "5432"
    }
    
    def get_db_connection():
        return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Создание таблиц
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            role_id SERIAL PRIMARY KEY,
            role_name VARCHAR(50) UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            full_name VARCHAR(150) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role_id INTEGER REFERENCES roles(role_id),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_id SERIAL PRIMARY KEY,
            category_name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS priorities (
            priority_id SERIAL PRIMARY KEY,
            priority_name VARCHAR(50) UNIQUE NOT NULL,
            response_hours INTEGER NOT NULL CHECK (response_hours > 0)
        );

        CREATE TABLE IF NOT EXISTS statuses (
            status_id SERIAL PRIMARY KEY,
            status_name VARCHAR(50) UNIQUE NOT NULL,
            is_closed BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order SMALLINT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS requests (
            request_id SERIAL PRIMARY KEY,
            request_number VARCHAR(20) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER REFERENCES users(user_id),
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(category_id),
            priority_id INTEGER REFERENCES priorities(priority_id),
            status_id INTEGER REFERENCES statuses(status_id),
            assigned_to INTEGER REFERENCES users(user_id),
            due_at TIMESTAMP,
            closed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS request_comments (
            comment_id SERIAL PRIMARY KEY,
            request_id INTEGER REFERENCES requests(request_id),
            author_id INTEGER REFERENCES users(user_id),
            comment_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS request_history (
            history_id SERIAL PRIMARY KEY,
            request_id INTEGER REFERENCES requests(request_id),
            changed_by INTEGER REFERENCES users(user_id),
            old_status_id INTEGER REFERENCES statuses(status_id),
            new_status_id INTEGER REFERENCES statuses(status_id),
            change_note TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Заполнение начальными данными
    cur.execute("SELECT COUNT(*) FROM roles")
    if cur.fetchone()['count'] == 0:
        cur.execute("INSERT INTO roles (role_name) VALUES ('Заявитель'), ('Исполнитель'), ('Администратор')")
        cur.execute("INSERT INTO categories (category_name) VALUES ('IT'), ('Бухгалтерия'), ('Административное'), ('Другое')")
        cur.execute("INSERT INTO priorities (priority_name, response_hours) VALUES ('Низкий', 72), ('Средний', 24), ('Высокий', 4)")
        cur.execute("INSERT INTO statuses (status_name, is_closed, sort_order) VALUES ('Новая', FALSE, 1), ('В работе', FALSE, 2), ('На проверке', FALSE, 3), ('Выполнена', TRUE, 4)")

        # Тестовые пользователи: пароль admin123
        hashed_pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
        cur.execute("""
            INSERT INTO users (full_name, email, password_hash, role_id) VALUES
            ('Администратор', 'admin@admin.com', %s, (SELECT role_id FROM roles WHERE role_name='Администратор')),
            ('Иванов Иван', 'executor@test.com', %s, (SELECT role_id FROM roles WHERE role_name='Исполнитель')),
            ('Петров Петр', 'user@test.com', %s, (SELECT role_id FROM roles WHERE role_name='Заявитель'))
        """, (hashed_pw, hashed_pw, hashed_pw))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ База данных успешно создана и заполнена!")

if __name__ == "__main__":
    init_db()
