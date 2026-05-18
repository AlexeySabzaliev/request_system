import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_login_page():
    """Тест: страница входа доступна"""
    response = client.get("/login")
    assert response.status_code == 200
    assert "Вход" in response.text

def test_root_redirect():
    """Тест: корневой URL перенаправляет на логин"""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307 or response.status_code == 302

def test_static_imports():
    """Тест: основные модули импортируются"""
    import database
    import main
    assert hasattr(main, 'app')
    assert True

def test_database_connection():
    """Тест: конфигурация БД существует"""
    from database import DB_CONFIG, get_db_connection
    assert DB_CONFIG is not None
    print("✅ Конфигурация БД загружена")

def test_app_exists():
    """Тест: приложение создано"""
    from main import app
    assert app is not None
    assert app.title == "ИС Обработки Заявок"

if __name__ == "__main__":
    pytest.main(["-v"])
