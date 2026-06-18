# Если твой core.py лежит внутри папки app, импорт будет таким:
from app.core import mask_all 

test_cases = [
    # 1. Проверка маскирования имен и стандартных email (исправленный баг с именами)
    "Hello, my name is John Doe and my email is john.doe@example.com.",
    
    # 2. Проверка обфусцированных email и европейских телефонов
    "Call Jane Smith at +49 170 1234567 or write to jane(at)domain[dot]com.",
    
    # 3. Проверка ложных срабатываний (исправленный баг с пробелами вокруг 'at')
    "We are at room 5. Please look at the document.",
    
    # 4. Проверка 'белого списка' навыков (они не должны маскироваться)
    "I am a developer skilled in Python, Docker, and AWS."
]

print("=== ЗАПУСК ТЕСТОВ МАСКИРОВАНИЯ ===")
for i, text in enumerate(test_cases, 1):
    print(f"\n[Тест {i}] Исходный: {text}")
    try:
        result = mask_all(text)
        print(f"[Тест {i}] Результат: {result}")
    except Exception as e:
        print(f"[Тест {i}] ОШИБКА: {e}")