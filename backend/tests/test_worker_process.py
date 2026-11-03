import subprocess
import sys


def test_worker_module_imports_in_a_fresh_interpreter() -> None:
    """Os testes carregam todos os modelos; o worker roda sozinho e precisa carregá-los também."""
    code = (
        "import app.worker as w; from sqlalchemy.orm import configure_mappers; "
        "configure_mappers(); "
        "from app.core.db import Base; "
        "Base.metadata.tables['vetsys.reminder_jobs'].foreign_keys and print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
