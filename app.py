import json
import os
import sys
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

import rumps
from AppKit import NSAlertFirstButtonReturn, NSApp, NSTextField, NSView
from Cocoa import NSAlert, NSComboBox, NSPoint, NSRect, NSSize, NSScreen


class StopwatchApp(rumps.App):
    """
    A menu bar stopwatch application that tracks time spent on various categories.

    Features:
    - Start, pause, and reset a stopwatch.
    - Maintain categories for time entries.
    - Save entries with timestamps and categories to a JSON data file.
    - View statistics (daily, weekly, lifetime) for each category.
    - Option to start the app at login.
    - Manual data entry for custom timestamps and durations.
    """

    APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "StopwatchApp"
    SETTINGS_FILENAME = "settings.json"
    DATA_FILENAME = "data.json"

    def __init__(self):
        super().__init__("0:00:00", quit_button="Quit")

        self.time_elapsed = 0
        self.running = False
        self.start_at_startup = False

        self.timer = rumps.Timer(self.update_time, 1)
        self.settings_path = self.get_settings_path()
        self.data_path = self.get_data_path()
        self.data = {}

        self.load_settings()
        self.load_data()

        # Build menu
        settings_item = rumps.MenuItem("Settings")
        settings_item.add(
            rumps.MenuItem("Start at startup", callback=self.toggle_startup)
        )
        settings_item.add(rumps.MenuItem("Add Category", callback=self.add_category))
        settings_item.add(
            rumps.MenuItem("Open Data File Location", callback=self.open_data_location)
        )

        self.menu = [
            "Start/Resume",
            "Pause",
            "Reset and Save",
            None,
            settings_item,
            rumps.MenuItem("Manual Entry", callback=self.add_entry),
            rumps.MenuItem("Statistics", callback=self.show_statistics),
        ]

        self.menu["Settings"]["Start at startup"].state = self.start_at_startup
        self.build_categories_menu()

    def get_settings_path(self) -> Path:
        """Ensure the application support directory exists and return the settings file path."""
        self.APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        return self.APP_SUPPORT_DIR / self.SETTINGS_FILENAME

    def get_data_path(self) -> Path:
        """Return the data file path."""
        return self.APP_SUPPORT_DIR / self.DATA_FILENAME

    def load_settings(self) -> None:
        """Load settings from JSON file."""
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
                self.start_at_startup = settings.get("start_at_startup", False)
        except FileNotFoundError:
            pass

    def save_settings(self) -> None:
        """Save settings to JSON file."""
        settings = {
            "start_at_startup": self.start_at_startup,
        }
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

    def load_data(self) -> None:
        """Load data from JSON file, creating it if it doesn't exist."""
        if not self.data_path.exists():
            data = {"categories": {}}
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        with open(self.data_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def save_data(self) -> None:
        """Save data to JSON file."""
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def build_categories_menu(self):
        keep_items = {
            "Start/Resume",
            "Pause",
            "Reset and Save",
            "Settings",
            "Manual Entry",
            "Statistics",
            "Quit",  # Include Quit here
        }

        # Remove old categories
        for key in list(self.menu.keys()):
            if key not in keep_items and key in self.menu:
                del self.menu[key]

        # Add categories
        insert_after = "Statistics"
        for cat in self.data["categories"].keys():
            cat_item = rumps.MenuItem(cat)
            delete_item = rumps.MenuItem(
                "Delete Category", callback=partial(self.delete_category, cat)
            )
            cat_item.add(delete_item)
            self.menu.insert_after(insert_after, cat_item)
            insert_after = cat

    def open_data_location(self, _) -> None:
        """Open the data file location in Finder."""
        os.system(f'open "{self.data_path}"')

    def update_time(self, _) -> None:
        """Update the displayed time each second when the stopwatch is running."""
        self.time_elapsed += 1
        self.title = self.format_time(self.time_elapsed)

    def format_time(self, seconds: int) -> str:
        """Format seconds as H:MM:SS."""
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hrs}:{mins:02d}:{secs:02d}"

    def format_time_minutes(self, minutes: float) -> str:
        """Format minutes as H:MM.mm."""
        hrs = int(minutes) // 60
        mins = minutes - (hrs * 60)
        return f"{hrs}:{mins:05.2f}"

    @rumps.clicked("Start/Resume")
    def start_resume(self, _) -> None:
        """Start or resume the timer."""
        if not self.running:
            self.timer.start()
            self.running = True

    @rumps.clicked("Pause")
    def pause(self, _) -> None:
        """Pause the timer."""
        if self.running:
            self.timer.stop()
            self.running = False

    @rumps.clicked("Reset and Save")
    def reset_and_save(self, _) -> None:
        """Reset the timer and save the current recorded time to a category."""
        self.timer.stop()
        self.running = False
        self.save_to_json()
        self.time_elapsed = 0
        self.title = "0:00:00"

    def toggle_startup(self, sender) -> None:
        """Toggle whether the app starts at login."""
        sender.state = not sender.state
        self.start_at_startup = sender.state
        self.save_settings()
        if self.start_at_startup:
            self.add_to_login_items()
        else:
            self.remove_from_login_items()

    def add_to_login_items(self) -> None:
        """Add this app to the user's login items."""
        app_path = os.path.abspath(sys.argv[0])
        script = f"""
        tell application "System Events"
            if not (exists login item "StopwatchApp") then
                make login item at end with properties {{path:"{app_path}", hidden:false}}
            end if
        end tell
        """
        os.system(f"osascript -e '{script}'")

    def remove_from_login_items(self) -> None:
        """Remove this app from the user's login items."""
        script = """
        tell application "System Events"
            delete login item "StopwatchApp"
        end tell
        """
        os.system(f"osascript -e '{script}'")

    def save_to_json(self) -> None:
        """
        Save the current elapsed time to the selected category in data.json.
        Prompts the user to select a category.
        """
        if not self.data["categories"]:
            rumps.alert("No categories available. Please add a category first.")
            return

        category_name = self.select_category(list(self.data["categories"].keys()))
        if not category_name:
            return

        time_value = round(self.time_elapsed / 60, 2)
        entry = {"date": datetime.now().isoformat(), "time": time_value}
        self.data["categories"][category_name].append(entry)
        self.save_data()
        rumps.notification(
            "Stopwatch", "Data Saved", f"Time saved under '{category_name}'."
        )

    def select_category(self, categories: list) -> str:
        """
        Display a dialog with a combo box to select a category.

        :param categories: A list of category names.
        :return: The selected category name or None if cancelled.
        """
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

        # Set the position of the alert
        alert_window = alert.window()
        screen_frame = NSScreen.mainScreen().frame()
        alert_width = 600  
        alert_height = 200 

        alert_x = (screen_frame.size.width - alert_width)
        alert_y = (screen_frame.size.height - alert_height) 
        alert_window.setFrame_display_animate_(
            NSRect(NSPoint(alert_x, alert_y), NSSize(alert_width, alert_height)), True, False
        )

        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        alert.window().setInitialFirstResponder_(combobox)
        response = alert.runModal()

        if response == NSAlertFirstButtonReturn:
            return combobox.stringValue()
        return None

    def get_text_input(self, title: str, message: str) -> str:
        """
        Prompt the user for text input.

        :param title: The dialog title.
        :param message: The dialog informative text.
        :return: The entered text or None if cancelled.
        """
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        width = 300
        height = 24
        textfield = NSTextField.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(width, height))
        )
        alert.setAccessoryView_(textfield)

        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        alert.window().setInitialFirstResponder_(textfield)

        response = alert.runModal()
        if response == NSAlertFirstButtonReturn:
            return textfield.stringValue().strip()
        return None

    def get_date_time_input(self):
        """
        Prompt the user for a date/time and a time duration in minutes.

        :return: A tuple (datetime object, float minutes) or (None, None) if invalid or cancelled.
        """
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Manual Entry")
        alert.setInformativeText_(
            "Enter a date/time (mm/dd/yy hh:mm) and time in minutes:"
        )
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        container_width = 300
        container_height = 60
        current_dt_str = datetime.now().strftime("%m/%d/%y %H:%M")

        datetime_field = NSTextField.alloc().initWithFrame_(
            NSRect(NSPoint(0, 30), NSSize(container_width, 24))
        )
        datetime_field.setStringValue_(current_dt_str)

        time_field = NSTextField.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(container_width, 24))
        )
        time_field.setPlaceholderString_("Time in minutes")

        container_view = NSView.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(container_width, container_height))
        )
        container_view.addSubview_(time_field)
        container_view.addSubview_(datetime_field)
        alert.setAccessoryView_(container_view)

        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        alert.window().setInitialFirstResponder_(datetime_field)

        response = alert.runModal()
        if response == NSAlertFirstButtonReturn:
            datetime_str = datetime_field.stringValue().strip()
            time_str = time_field.stringValue().strip()
            try:
                date_value = datetime.strptime(datetime_str, "%m/%d/%y %H:%M")
                time_minutes = float(time_str)
                return date_value, time_minutes
            except (ValueError, TypeError):
                return None, None
        return None, None

    def delete_category(self, category_name, _) -> None:
        """
        Delete a category by name.

        :param category_name: The category to delete.
        """
        if category_name in self.data["categories"]:
            del self.data["categories"][category_name]
            self.save_data()
            self.build_categories_menu()

    def add_category(self, _) -> None:
        """Prompt the user to add a new category."""
        name = self.get_text_input("Add Category", "Enter category name:")
        if name:
            if name not in self.data["categories"]:
                self.data["categories"][name] = []
                self.save_data()
                self.build_categories_menu()
            else:
                rumps.alert("Category already exists.")

    def add_entry(self, _) -> None:
        """Prompt the user to add a manual time entry."""
        if not self.data["categories"]:
            rumps.alert("No categories available. Please add a category first.")
            return

        category_name = self.select_category(list(self.data["categories"].keys()))
        if not category_name:
            return

        date_value, time_minutes = self.get_date_time_input()
        if date_value is None or time_minutes is None:
            return

        entry = {"date": date_value.isoformat(), "time": time_minutes}
        self.data["categories"][category_name].append(entry)
        self.save_data()
        rumps.notification(
            "Stopwatch", "Data Saved", f"Entry saved under '{category_name}'."
        )

    def format_hours_minutes_seconds(self, minutes: float) -> str:
        """Format time in minutes as H:MM:SS."""
        total_seconds = int(round(minutes * 60))
        hrs = total_seconds // 3600
        mins = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hrs}:{mins:02d}:{secs:02d}"

    def show_statistics(self, _) -> None:
        """Show statistics for each category (daily, weekly, lifetime) with detailed time formatting."""
        if not self.data["categories"]:
            rumps.alert("No categories available to show statistics.")
            return

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        per_category_stats = {}
        overall_daily = 0
        overall_weekly = 0
        overall_lifetime = 0  # Initialize overall lifetime total

        for category, entries in self.data["categories"].items():
            daily = 0
            weekly = 0
            lifetime = 0

            for entry in entries:
                try:
                    entry_date = datetime.fromisoformat(entry["date"]).date()
                except ValueError:
                    continue

                time_spent = entry["time"]
                lifetime += time_spent

                if entry_date == today:
                    daily += time_spent

                if week_ago <= entry_date <= today:
                    weekly += time_spent

            per_category_stats[category] = {
                "daily": daily,
                "weekly": weekly,
                "lifetime": lifetime,
            }

            overall_daily += daily
            overall_weekly += weekly
            overall_lifetime += lifetime

        stats = "Stopwatch Statistics:\n\n"
        for category, stats_dict in per_category_stats.items():
            stats += f"{category}\n"
            stats += f"  Daily Total: {self.format_hours_minutes_seconds(stats_dict['daily'])}\n"
            stats += f"  Weekly Total: {self.format_hours_minutes_seconds(stats_dict['weekly'])}\n"
            stats += f"  Lifetime Total: {self.format_hours_minutes_seconds(stats_dict['lifetime'])}\n\n"

        stats += (
            f"Overall Daily Total: {self.format_hours_minutes_seconds(overall_daily)}\n"
        )
        stats += f"Overall Weekly Total: {self.format_hours_minutes_seconds(overall_weekly)}\n"
        stats += f"Overall Lifetime Total: {self.format_hours_minutes_seconds(overall_lifetime)}\n"

        rumps.alert(stats, "Stopwatch Statistics")


if __name__ == "__main__":
    app = StopwatchApp()
    app.run()
