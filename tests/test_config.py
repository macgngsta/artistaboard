"""Config guards: the insecure dev secret must not survive into a non-dev deployment."""

import pytest
from pydantic import ValidationError

from artistaboard.config import Settings


def test_dev_default_secret_allowed_in_dev():
    # The bundled default is fine when APP_ENV is dev (the default).
    s = Settings(_env_file=None)
    assert s.app_env == "dev"
    assert s.encryption_secret == s.session_secret


def test_dev_default_secret_rejected_outside_dev():
    with pytest.raises(ValidationError, match="insecure dev default"):
        Settings(_env_file=None, app_env="prod")


def test_real_secret_accepted_outside_dev():
    s = Settings(_env_file=None, app_env="prod", session_secret="a-real-and-secret-value")
    assert s.session_secret == "a-real-and-secret-value"
    # encryption falls back to the (now real) session secret unless a dedicated key is set.
    assert s.encryption_secret == "a-real-and-secret-value"
