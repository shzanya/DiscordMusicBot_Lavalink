"""
Скрипт для удаления комментариев
"""

import os
from pathlib import Path


def remove_comments_from_file(file_path: Path) -> bool:
    """
    Удаляет комментарии
    Возвращает True если файл был изменен
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        lines = content.split("\n")
        new_lines = []

        for line in lines:
            if '"""' in line or "'''" in line:
                new_lines.append(line)
                continue

            if "#" in line:
                quote_count = 0
                comment_pos = -1

                for i, char in enumerate(line):
                    if char in ['"', "'"]:
                        if quote_count == 0:
                            quote_count = 1
                        else:
                            quote_count = 0
                    elif char == "#" and quote_count == 0:
                        comment_pos = i
                        break

                if comment_pos != -1:
                    line = line[:comment_pos].rstrip()

            new_lines.append(line)

        new_content = "\n".join(new_lines)

        new_content = new_content.rstrip()

        if new_content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True

        return False

    except Exception as e:
        print(f"Ошибка при обработке {file_path}: {e}")
        return False


def process_directory(directory: Path, extensions: list = None):
    """
    Обрабатывает все файлы в директории и поддиректориях
    """
    if extensions is None:
        extensions = [".py"]

    processed_files = 0
    modified_files = 0

    for root, dirs, files in os.walk(directory):
        skip_dirs = ["__pycache__", "venv", "env"]
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip_dirs]

        for file in files:
            file_path = Path(root) / file

            if any(file.endswith(ext) for ext in extensions):
                processed_files += 1
                print(f"Обрабатываю: {file_path}")

                if remove_comments_from_file(file_path):
                    modified_files += 1
                    print(f"  ✓ Изменен: {file_path}")
                else:
                    print(f"  - Без изменений: {file_path}")

    return processed_files, modified_files


def main():
    """
    Основная функция
    """
    print("=== Удаление комментариев # из Python файлов ===\n")

    current_dir = Path.cwd()
    print(f"Рабочая директория: {current_dir}")

    response = input("\nПродолжить? (y/N): ").strip().lower()
    if response not in ["y", "yes", "да"]:
        print("Отменено.")
        return

    print("\nНачинаю обработку...\n")

    processed, modified = process_directory(current_dir)

    print("\n=== Результат ===")
    print(f"Обработано файлов: {processed}")
    print(f"Изменено файлов: {modified}")
    print(f"Файлов без изменений: {processed - modified}")

    if modified > 0:
        print(f"\n✓ Комментарии успешно удалены из {modified} файлов!")
    else:
        print("\n- Комментарии не найдены или файлы не изменились.")


if __name__ == "__main__":
    main()