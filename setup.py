# setup.py
from setuptools import setup

APP = ['app.py']  # Ensure this matches your main script's name
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,  # Makes the app a background-only app (no Dock icon)
        'CFBundleName': 'StopwatchApp',
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleVersion': '0.1.0',
        'CFBundleIdentifier': 'com.yourname.stopwatchapp',  # Replace with your unique identifier
    },
    'packages': ['rumps', 'openpyxl', 'Cocoa', 'AppKit'],
    # 'iconfile': 'app.icns',  # Optional: specify your app icon
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
