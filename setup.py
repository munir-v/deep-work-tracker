from setuptools import setup

APP = ['app.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,  # Hides the dock icon, keeping the app in the menu bar
        'CFBundleName': 'StopwatchApp',
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '1.0',
        'NSPrincipalClass': 'NSApplication',
    },
    'packages': ['rumps', 'AppKit', 'Cocoa'],  # Includes necessary dependencies
    'includes': ['json', 'os', 'sys', 'datetime', 'functools', 'pathlib'],  # Ensure included modules
    'excludes': ['tkinter', 'unittest','Carbon'],  # Exclude unused modules to reduce bundle size
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)