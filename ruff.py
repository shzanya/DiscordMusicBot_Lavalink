#!/usr/bin/env python3
"""
Автоматическое исправление кода с помощью ruff.
Исправляет все найденные проблемы в проекте.
"""

import subprocess
import sys


def run_ruff_fix():
    """Запускает ruff для автоматического исправления кода."""
    print("🔧 Запуск автоматического исправления кода...")

    try:
        # Проверяем, установлен ли ruff
        result = subprocess.run(
            ["ruff", "--version"], capture_output=True, text=True, check=False
        )

        if result.returncode != 0:
            print("❌ Ruff не установлен. Устанавливаем...")
            subprocess.run([sys.executable, "-m", "pip", "install", "ruff"], check=True)
            print("✅ Ruff установлен!")

        # Сначала показываем все проблемы
        print("\n📋 Найденные проблемы:")
        subprocess.run(["ruff", "check", "."], check=False)

        # Автоматически исправляем все что можно
        print("\n🔧 Исправляем проблемы автоматически...")
        result = subprocess.run(
            ["ruff", "check", ".", "--fix"], capture_output=True, text=True, check=False
        )

        if result.returncode == 0:
            print("✅ Все проблемы исправлены автоматически!")
        else:
            print(
                "⚠️ Некоторые проблемы исправлены, но остались те, что требуют ручного исправления"
            )
            print(result.stdout)

        # Показываем что осталось
        print("\n📋 Оставшиеся проблемы:")
        subprocess.run(["ruff", "check", "."], check=False)

        # Форматируем код
        print("\n🎨 Форматируем код...")
        subprocess.run(["ruff", "format", "."], check=False)
        print("✅ Код отформатирован!")

    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при выполнении команды: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

    return True


def run_ruff_check_only():
    """Только проверка кода без исправления."""
    print("🔍 Проверка кода...")
    subprocess.run(["ruff", "check", "."], check=False)


def run_ruff_format_only():
    """Только форматирование кода."""
    print("🎨 Форматирование кода...")
    subprocess.run(["ruff", "format", "."], check=False)


def main():
    """Главная функция."""
    print("🚀 Ruff Code Fixer")
    print("=" * 50)

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "check":
            run_ruff_check_only()
        elif command == "format":
            run_ruff_format_only()
        elif command == "fix":
            run_ruff_fix()
        elif command == "help":
            print_help()
        else:
            print(f"❌ Неизвестная команда: {command}")
            print_help()
    else:
        # По умолчанию запускаем полное исправление
        run_ruff_fix()


def print_help():
    """Показывает справку по использованию."""
    print("""
Использование: python ruff.py [команда]

Команды:
  check   - Только проверка кода (без исправления)
  format  - Только форматирование кода
  fix     - Полное исправление и форматирование (по умолчанию)
  help    - Показать эту справку

Примеры:
  python ruff.py          # Полное исправление
  python ruff.py check    # Только проверка
  python ruff.py format   # Только форматирование
  python ruff.py fix      # Явно указать исправление
    """)


if __name__ == "__main__":
    main()
