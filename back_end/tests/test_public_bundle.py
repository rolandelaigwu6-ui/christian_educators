"""Deployment must publish public assets without exposing source or credentials."""
import importlib.util
from pathlib import Path


def test_public_bundle_excludes_private_files_and_rejects_symlinks(tmp_path):
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'prepare_public.py'
    assert script.exists(), 'A public-only deployment bundle is required'
    spec = importlib.util.spec_from_file_location('prepare_public', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / 'source'
    source.mkdir()
    for name in ['index.html', '404.html', 'robots.txt']:
        (source / name).write_text('public')
    (source / 'pages').mkdir()
    (source / 'pages' / 'about.html').write_text('public')
    (source / 'pages' / '.env').write_text('secret')
    (source / 'assets').mkdir()
    (source / 'assets' / 'main.js').write_text('public')
    (source / 'assets' / 'database.db').write_text('secret')
    (source / '.env').write_text('secret')
    (source / 'back_end.py').write_text('private code')
    destination = tmp_path / 'public'
    module.prepare(source, destination)
    assert (destination / 'index.html').exists()
    assert (destination / 'pages' / 'about.html').exists()
    assert (destination / 'assets' / 'main.js').exists()
    assert not (destination / '.env').exists()
    assert not (destination / 'back_end.py').exists()
    assert not (destination / 'pages' / '.env').exists()
    assert not (destination / 'assets' / 'database.db').exists()
    (source / 'assets' / 'leak.js').symlink_to(source / '.env')
    import pytest
    with pytest.raises(ValueError, match='[Ss]ymlink'):
        module.prepare(source, destination)


def test_vercel_entrypoint_serves_public_pages_without_database_startup():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('prepare_entrypoint_public', root / 'scripts' / 'prepare_public.py')
    bundle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle)
    bundle.prepare(root, root / 'public')
    from fastapi.testclient import TestClient
    from app import app
    # No lifespan: static files must not require the API database to be ready.
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    assert 'COCEGN' in response.text
    assert client.get('/pages/member-login.html').status_code == 200
    assert client.get('/assets/js/main.js').status_code == 200
    for path in ['/back_end/.env', '/.git/config', '/Agent.md', '/missing-page']:
        assert client.get(path).status_code == 404
    assert client.get('/auth/me').status_code == 401
