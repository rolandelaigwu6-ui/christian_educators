"""Configuration-loading tests.

Regression guard for the bug where `back_end.py` read its configuration with
`os.getenv` but nothing ever loaded a `.env` file. A developer could follow
README.md exactly, create `back_end/.env`, and still get no SMTP configuration
-- so every email silently printed to the terminal instead of being sent.

`back_end.py` captures its configuration at import time, so these tests control
the environment and reimport the module rather than assuming a clean cache.
"""

import importlib
import sys
from pathlib import Path

BACK_END_DIR = Path(__file__).resolve().parents[1]
if str(BACK_END_DIR) not in sys.path:
    sys.path.insert(0, str(BACK_END_DIR))


def test_config_is_read_from_env_file(tmp_path, monkeypatch):
    """Settings in the .env file must reach the module's configuration.

    ENV_FILE lets the test point at a temporary file so the developer's real
    back_end/.env is never touched.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SMTP_HOST=smtp.example.test\n"
        "SMTP_FROM_EMAIL=mail@example.test\n",
        encoding="utf-8",
    )

    # Nothing may leak in from the ambient environment.
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM_EMAIL", raising=False)
    monkeypatch.setenv("ENV_FILE", str(env_file))

    import back_end

    module = importlib.reload(back_end)

    assert module.SMTP_HOST == "smtp.example.test"
    assert module.SMTP_FROM_EMAIL == "mail@example.test"


def test_real_environment_variables_override_the_env_file(tmp_path, monkeypatch):
    """An exported variable must win over the .env file.

    load_dotenv's default is not to override, which is what makes it safe to
    keep a .env on disk while overriding one value in the shell.
    """
    env_file = tmp_path / ".env"
    env_file.write_text("SMTP_HOST=from-the-file\n", encoding="utf-8")

    monkeypatch.setenv("ENV_FILE", str(env_file))
    monkeypatch.setenv("SMTP_HOST", "from-the-shell")

    import back_end

    module = importlib.reload(back_end)

    assert module.SMTP_HOST == "from-the-shell"


def test_missing_env_file_is_not_an_error(tmp_path, monkeypatch):
    """A deployment with no .env at all must still start.

    Configuration can come entirely from the real environment, so an absent
    file is a normal condition, not a crash.
    """
    monkeypatch.setenv("ENV_FILE", str(tmp_path / "does-not-exist.env"))
    monkeypatch.delenv("SMTP_HOST", raising=False)

    import back_end

    module = importlib.reload(back_end)

    assert module.SMTP_HOST is None
