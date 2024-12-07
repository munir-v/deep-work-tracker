import rumps
import json
from datetime import datetime, timedelta
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
        # Initialize the App with the quit_button parameter
        super(StopwatchApp, self).__init__("0:00:00", quit_button="Quit")

        self.time_elapsed = 0
        self.timer = rumps.Timer(self.update_time, 1)
        self.running = False

        self.start_at_startup = False
        self.settings_path = self.get_settings_path()
        self.data_path = self.get_data_path()
        self.load_settings()
        self.load_data()

        # Define the menu without including the Quit button
        self.menu = [
            "Start/Resume",
            "Pause",
            "Reset and Save",
            None,
            rumps.MenuItem("Start at startup", callback=self.toggle_startup),
            rumps.MenuItem("Add Category", callback=self.add_category),
            rumps.MenuItem("Statistics", callback=self.show_statistics),  # Added Statistics
        ]

        # Set the state for "Start at startup"
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
        # Remove any existing categories (only categories, don't remove known items)
        keep_items = {"Start/Resume", "Pause", "Reset and Save", "Start at startup", "Add Category", "Statistics"}
        for key in list(self.menu.keys()):
            if key not in keep_items and key in self.menu:
                del self.menu[key]

        # Add categories after "Add Category"
        insert_after = "Add Category"
        for cat in self.data["categories"].keys():
            cat_item = rumps.MenuItem(cat)
            delete_item = rumps.MenuItem("Delete Category", callback=partial(self.delete_category, cat))
            cat_item.add(delete_item)
            self.menu.insert_after(insert_after, cat_item)
            insert_after = cat  # Ensure subsequent categories are added in order

    def update_time(self, _):
        self.time_elapsed += 1
        self.title = self.format_time(self.time_elapsed)

    def format_time(self, seconds):
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hrs}:{mins:02d}:{secs:02d}"

    def format_time_minutes(self, minutes):
        hrs = int(minutes) // 60
        mins = minutes - (hrs * 60)
        return f"{hrs}:{mins:05.2f}"  # e.g., 1:23.45

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

    @rumps.clicked("Statistics")
    def show_statistics(self, _):
        if not self.data["categories"]:
            rumps.alert("No categories available to show statistics.")
            return

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        per_category_stats = {}
        overall_daily = 0
        overall_weekly = 0

        for category, entries in self.data["categories"].items():
            daily = 0
            weekly = 0
            lifetime = 0

            for entry in entries:
                try:
                    entry_date = datetime.fromisoformat(entry['date']).date()
                except ValueError:
                    continue  # Skip invalid date formats

                time = entry['time']  # in minutes
                lifetime += time

                if entry_date == today:
                    daily += time

                if week_ago <= entry_date <= today:
                    weekly += time

            per_category_stats[category] = {
                'daily': daily,
                'weekly': weekly,
                'lifetime': lifetime
            }

            overall_daily += daily
            overall_weekly += weekly

        # Compile the statistics string
        stats = "Stopwatch Statistics:\n\n"

        for category, stats_dict in per_category_stats.items():
            stats += f"Category: {category}\n"
            stats += f"  Daily Total: {self.format_time_minutes(stats_dict['daily'])} minutes\n"
            stats += f"  Weekly Total: {self.format_time_minutes(stats_dict['weekly'])} minutes\n"
            stats += f"  Lifetime Total: {self.format_time_minutes(stats_dict['lifetime'])} minutes\n\n"

        stats += f"Overall Daily Total: {self.format_time_minutes(overall_daily)} minutes\n"
        stats += f"Overall Weekly Total: {self.format_time_minutes(overall_weekly)} minutes\n"

        # Display the statistics in an alert
        rumps.alert(stats, "Stopwatch Statistics")  # Changed here


if __name__ == "__main__":
    app = StopwatchApp()
    app.run()
