from setuptools import setup

APP = ["app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "LSUIElement": True,
    },
    "packages": ["rumps", "AppKit", "Cocoa"],
    "includes": ["imp"],
    "iconfile": "icons/icon.icns",
}

setup(
    name="Deep Work Tracker",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
