from setuptools import setup

APP = ['app.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,  # Hides the dock icon, keeping the app in the menu bar
    },
    'packages': ['rumps', 'AppKit', 'Cocoa'],  # Includes necessary dependencies
    'includes': ['imp'],
}

setup(
    name='Deep Work Tracker',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)