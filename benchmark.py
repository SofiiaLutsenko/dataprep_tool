import time
import os
from app.core import mask_all  # Import your masking function

def generate_heavy_text():
    """Generates a dense PII text (~99 KB) to stress test the system"""
    base_sample = (
        "John Doe, email: john.doe@example.com, phone: +49 151 12345678, born 12/12/1995. "
        "Worked at Acme Corp from 2019 to 2022. Age: 30. Location: Munich, Germany. "
        "Jane Smith, smith.j@gmail.com, DOB: 01.01.1990, +380671234567. "
    )
    # Repeat the base string to reach approximately 99,000 bytes (99 KB)
    iterations = 99000 // len(base_sample)
    return base_sample * iterations

def run_benchmark():
    print("=== ЗАПУСК БЕНЧМАРКА ВЕРСИИ 1.4 ===")
    
    # 1. Generate test data
    text = generate_heavy_text()
    text_size_kb = len(text.encode('utf-8')) / 1024
    print(f"Размер сгенерированного текста для теста: {text_size_kb:.2f} KB")
    
    # 2. Warmup run (spaCy model loading overhead happens on the first call)
    print("Загрузка модели и первый запуск (прогрев)...")
    start_warmup = time.perf_counter()
    _ = mask_all(text)
    warmup_time = time.perf_counter() - start_warmup
    print(f"Время первого 'холодного' запуска: {warmup_time:.4f} сек")
    
    # 3. Main benchmark loop (5 iterations of pure processing)
    print("Запуск основного теста (5 итераций)...")
    times = []
    for i in range(1, 6):
        start_run = time.perf_counter()
        _ = mask_all(text)
        end_run = time.perf_counter() - start_run
        times.append(end_run)
        print(f"  Итерация #{i}: {end_run:.4f} сек")
    
    # 4. Calculate final metrics
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print("\n=== ИТОГОВЫЕ РЕЗУЛЬТАТЫ ===")
    print(f"Минимальное время обработки: {min_time:.4f} сек")
    print(f"Максимальное время обработки: {max_time:.4f} сек")
    print(f"Среднее время (чистая скорость): {avg_time:.4f} сек")
    print("=========================================")

if __name__ == "__main__":
    run_benchmark()