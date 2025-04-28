from pathlib import Path

def find_project_root(current_path: Path = Path(__file__)) -> Path:
    """
    Находит корень проекта по наличию файла .project_root.
    """
    while not (current_path / ".project_root").exists():
        parent = current_path.parent
        if parent == current_path:  # Дошли до корня файловой системы
            raise FileNotFoundError("Project root not found. Create .project_root file in the root!")
        current_path = parent
    return current_path

PROJECT_ROOT = Path(__file__).parent.parent.parent