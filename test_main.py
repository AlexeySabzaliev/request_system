import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_import_main():
    """Тест: проверка импорта основного модуля"""
    try:
        import main
        assert hasattr(main, 'app')
        print("✅ main.py импортирован успешно")
    except Exception as e:
        pytest.fail(f"Ошибка импорта main.py: {e}")

def test_import_database():
    """Тест: проверка импорта модуля БД"""
    try:
        import database
        assert hasattr(database, 'get_db_connection')
        assert hasattr(database, 'init_db')
        assert hasattr(database, 'DB_CONFIG')
        print("✅ database.py импортирован успешно, DB_CONFIG найден")
    except Exception as e:
        pytest.fail(f"Ошибка импорта database.py: {e}")

def test_check_templates():
    """Тест: проверка наличия HTML-шаблонов"""
    template_dir = "templates"
    required_templates = [
        "login.html",
        "dashboard.html", 
        "requests.html",
        "request_form.html",
        "request_card.html"
    ]
    
    if not os.path.exists(template_dir):
        pytest.fail(f"Папка {template_dir} не найдена")
    
    for template in required_templates:
        template_path = os.path.join(template_dir, template)
        assert os.path.exists(template_path), f"Шаблон {template} не найден"
    
    print(f"✅ Все {len(required_templates)} шаблонов найдены")

def test_check_requirements():
    """Тест: проверка наличия requirements.txt"""
    assert os.path.exists("requirements.txt"), "requirements.txt не найден"
    print("✅ requirements.txt найден")

def test_syntax_check():
    """Тест: проверка синтаксиса Python файлов"""
    import subprocess
    files_to_check = ["main.py", "database.py"]
    
    for file in files_to_check:
        if not os.path.exists(file):
            pytest.skip(f"{file} не найден")
        
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", file],
            capture_output=True
        )
        assert result.returncode == 0, f"Синтаксическая ошибка в {file}: {result.stderr}"
    
    print("✅ Синтаксис всех файлов корректен")

def test_db_config_content():
    """Тест: проверка содержимого DB_CONFIG"""
    import database
    config = database.DB_CONFIG
    required_keys = ['dbname', 'user', 'password', 'host', 'port']
    for key in required_keys:
        assert key in config, f"Отсутствует ключ {key} в DB_CONFIG"
    print("✅ DB_CONFIG содержит все необходимые ключи")

if __name__ == "__main__":
    pytest.main(["-v"])
