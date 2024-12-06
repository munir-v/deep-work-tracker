import rumps
import json
from datetime import datetime
from Cocoa import (
    NSAlert,
    NSComboBox,
    NSPoint,
    NSRect,
    NSSize,
    NSApp,
)
from AppKit import NSAlertFirstButtonReturn
import os
from pathlib import Path
from functools import partial

class StopwatchApp(rumps.App):
    def __init__(self):
        # Ensure quit button is always at the end
        self.quit_button = "Quit"
        super(StopwatchApp, self).__init__("0:00:00")

        self.time_elapsed = 0
        self.timer = rumps.Timer(self.update_time, 1)
        self.running = False

        self.start_at_startup = False
        self.settings_path = self.get_settings_path()
        self.data_path = self.get_data_path()
        self.load_settings()
        self.load_data()

        self.menu = [
            "Start/Resume",
            "Pause",
            "Reset and Save",
            None,
            rumps.MenuItem("Start at startup", callback=self.toggle_startup),
            rumps.MenuItem("Add Category", callback=self.add_category)
        ]

        self.menu["Start at startup"].state = self.start_at_startup
        self.build_categories_menu()

    def get_settings_path(self):
        app_support = Path.home() / "Library" / "Application Support" / "StopwatchApp"
        app_support.mkdir(parents=True, exist_ok=True)
        return app_support / "settings.json"

    def get_data_path(self):
        app_support = Path.home() / "Library" / "Application Support" / "StopwatchApp"
        return app_support / "data.json"

    def load_settings(self):
        try:
            with open(self.settings_path, "r") as f:
                settings = json.load(f)
                self.start_at_startup = settings.get("start_at_startup", False)
        except FileNotFoundError:
            pass

    def save_settings(self):
        settings = {
            "start_at_startup": self.start_at_startup,
        }
        with open(self.settings_path, "w") as f:
            json.dump(settings, f)

    def load_data(self):
        if not self.data_path.exists():
            data = {"categories": {}}
            with open(self.data_path, "w") as f:
                json.dump(data, f)
        with open(self.data_path, "r") as f:
            self.data = json.load(f)

    def save_data(self):
        with open(self.data_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def build_categories_menu(self):
        # Remove any existing categories (only categories, don't remove known items or Quit)
        keep_items = {"Start/Resume", "Pause", "Reset and Save", "Start at startup", "Add Category", "Quit"}
        for key in list(self.menu.keys()):
            if key not in keep_items and key in self.menu:
                del self.menu[key]

        # Add categories after "Add Category"
        for cat in self.data["categories"].keys():
            cat_item = rumps.MenuItem(cat)
            delete_item = rumps.MenuItem("Delete Category", callback=partial(self.delete_category, cat))
            cat_item.add(delete_item)
            self.menu.insert_after("Add Category", cat_item)

    def update_time(self, _):
        self.time_elapsed += 1
        self.title = self.format_time(self.time_elapsed)

    def format_time(self, seconds):
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hrs}:{mins:02d}:{secs:02d}"

    @rumps.clicked("Start/Resume")
    def start_resume(self, _):
        if not self.running:
            self.timer.start()
            self.running = True

    @rumps.clicked("Pause")
    def pause(self, _):
        if self.running:
            self.timer.stop()
            self.running = False

    @rumps.clicked("Reset and Save")
    def reset_and_save(self, _):
        self.timer.stop()
        self.running = False
        self.save_to_json()
        self.time_elapsed = 0
        self.title = "0:00:00"

    def toggle_startup(self, sender):
        sender.state = not sender.state
        self.start_at_startup = sender.state
        self.save_settings()
        if self.start_at_startup:
            self.add_to_login_items()
        else:
            self.remove_from_login_items()

    def add_to_login_items(self):
        import sys
        app_path = os.path.abspath(sys.argv[0])
        script = f'''
        tell application "System Events"
            if not (exists login item "StopwatchApp") then
                make login item at end with properties {{path:"{app_path}", hidden:false}}
            end if
        end tell
        '''
        os.system(f"osascript -e '{script}'")

    def remove_from_login_items(self):
        script = '''
        tell application "System Events"
            delete login item "StopwatchApp"
        end tell
        '''
        os.system(f"osascript -e '{script}'")

    def save_to_json(self):
        if not self.data["categories"]:
            rumps.alert("No categories available. Please add a category first.")
            return

        category_name = self.select_category(list(self.data["categories"].keys()))
        if not category_name:
            return

        time_value = round(self.time_elapsed / 60, 2)
        entry = {
            "date": datetime.now().isoformat(),
            "time": time_value
        }
        self.data["categories"][category_name].append(entry)
        self.save_data()
        rumps.notification("Stopwatch", "Data Saved", f"Time saved under '{category_name}'.")

    def select_category(self, categories):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Select Category")
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        view_width = 300
        view_height = 24
        combobox = NSComboBox.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(view_width, view_height))
        )
        combobox.addItemsWithObjectValues_(categories)
        combobox.selectItemAtIndex_(0)
        alert.setAccessoryView_(combobox)

        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        alert.window().setInitialFirstResponder_(combobox)
        response = alert.runModal()
        if response == NSAlertFirstButtonReturn:
            return combobox.stringValue()
        else:
            return None

    def get_text_input(self, title, message):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        from AppKit import NSTextField
        width = 300
        height = 24
        textfield = NSTextField.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(width, height)))
        alert.setAccessoryView_(textfield)

        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        alert.window().setInitialFirstResponder_(textfield)

        response = alert.runModal()
        if response == NSAlertFirstButtonReturn:
            return textfield.stringValue().strip()
        return None

    def delete_category(self, category_name, _):
        if category_name in self.data["categories"]:
            del self.data["categories"][category_name]
            self.save_data()
            self.build_categories_menu()

    @rumps.clicked("Add Category")
    def add_category(self, _):
        name = self.get_text_input("Add Category", "Enter category name:")
        if name:
            if name not in self.data["categories"]:
                self.data["categories"][name] = []
                self.save_data()
                self.build_categories_menu()
            else:
                rumps.alert("Category already exists.")


if __name__ == "__main__":
    app = StopwatchApp()
    app.run()
