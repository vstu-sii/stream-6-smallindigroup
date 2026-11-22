def pytest_configure(config):
    config.addinivalue_line("markers", "fast: быстрый срез evals, блокирует мёрж")
