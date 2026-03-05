from platformdirs import user_data_path

DATA_DIR = user_data_path("mooshroom")
VERSIONS_DIR = DATA_DIR / "versions"
LIBRARIES_DIR = DATA_DIR / "libraries"
ASSETS_DIR = DATA_DIR / "assets"
JAVA_DIR = DATA_DIR / "java"
AUTH_FILE = DATA_DIR / "auth.json"
