import json
import os
import sys
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
import shutil

import rumps
from AppKit import NSAlertFirstButtonReturn, NSApp, NSTextField, NSView, NSSlider
from Cocoa import NSAlert, NSComboBox, NSPoint, NSRect, NSSize, NSScreen, NSObject

DEBUGGING_MODE = True


class SliderDelegate(NSObject):
    """Delegate class for handling slider changes in timer duration dialog."""
    def init(self):
        self = super().init()
        if self:
            self.label = None
        return self
    
    def setLabel_(self, label):
        """Set the label that should be updated when slider changes."""
        self.label = label
    
    def sliderChanged_(self, sender):
        minutes = int(sender.intValue())
        if self.label:
            self.label.setStringValue_(f"Current duration: {minutes} minutes")


class StopwatchApp(rumps.App):
    """
    A menu bar application that tracks time spent on various categories using both timer and stopwatch functionality.

    Features:
    - Start, pause, and reset both timer and stopwatch independently.
    - Maintain categories for time entries.
    - Save entries with timestamps and categories to a JSON data file.
    - View statistics (daily, weekly, lifetime) for each category.
    - Option to start the app at login.
    - Manual data entry for custom timestamps and durations.
    """

    APP_SUPPORT_DIR = (
        Path.home() / "Library" / "Application Support" / "Deep Work Timer"
    )
    SETTINGS_FILENAME = "settings.json"
    DATA_FILENAME = "data_debug.json" if DEBUGGING_MODE else "data.json"

    def __init__(self):
        super().__init__("0:00:00", quit_button="Quit")

        # Initialize paths and data
        self.settings_path = self.get_settings_path()
        self.data_path = self.get_data_path()
        self.data = {}
        self.start_at_startup = False

        # Timer settings
        self.timer_duration = 120 * 60  # 120 minutes in seconds
        self.time_remaining = self.timer_duration
        self.timer_running = False
        self.timer_paused = False
        self.timer = rumps.Timer(self.update_timer, 1)

        # Stopwatch settings
        self.time_elapsed = 0
        self.stopwatch_running = False
        self.stopwatch_paused = False
        self.stopwatch = rumps.Timer(self.update_stopwatch, 1)

        # Store original callbacks
        self.original_callbacks = {
            "Start Timer": self.start_resume_timer,
            "Pause Timer": self.pause_timer,
            "Reset and Save Timer": self.reset_and_save_timer,
            "Change Timer Duration": self.change_timer_duration,
            "Start Stopwatch": self.start_resume_stopwatch,
            "Pause Stopwatch": self.pause_stopwatch,
            "Reset and Save Stopwatch": self.reset_and_save_stopwatch
        }

        # Load saved data
        self.load_settings()
        self.load_data()

        # Build menu
        self.build_menu()
        self.build_categories_menu()

        # defer the initial menu update until after rumps finishes launching
        self._deferred_init = rumps.Timer(self._late_init, 0)
        self._deferred_init.start()

    def build_menu(self):
        """Build the main menu structure."""
        settings_item = rumps.MenuItem("Settings")
        settings_item.add(rumps.MenuItem("Start at startup", callback=self.toggle_startup))
        settings_item.add(rumps.MenuItem("Add Category", callback=self.add_category))
        settings_item.add(rumps.MenuItem("Open Data File", callback=self.open_data_location))
        settings_item.add(rumps.MenuItem("Open Support Directory", callback=self.open_app_support_dir))
        settings_item.add(rumps.MenuItem("Reload Data File", callback=self.reload_data))

        self.menu = [
            rumps.MenuItem("Start Timer", callback=self.start_resume_timer),
            rumps.MenuItem("Pause Timer", callback=self.pause_timer),
            rumps.MenuItem("Reset and Save Timer", callback=self.reset_and_save_timer),
            rumps.MenuItem("Change Timer Duration", callback=self.change_timer_duration),
            None,
            rumps.MenuItem("Start Stopwatch", callback=self.start_resume_stopwatch),
            rumps.MenuItem("Pause Stopwatch", callback=self.pause_stopwatch),
            rumps.MenuItem("Reset and Save Stopwatch", callback=self.reset_and_save_stopwatch),
            None,
            rumps.MenuItem("Manual Entry", callback=self.add_entry),
            rumps.MenuItem("Statistics", callback=self.show_statistics),
            rumps.MenuItem("Categories"),
            None,
            settings_item,
        ]

        self.menu["Settings"]["Start at startup"].state = self.start_at_startup

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
                self.timer_duration = settings.get("timer_minutes", 120) * 60
                # Update time_remaining to match the loaded timer duration
                self.time_remaining = self.timer_duration
        except FileNotFoundError:
            pass

    def save_settings(self) -> None:
        """Save settings to JSON file."""
        settings = {
            "start_at_startup": self.start_at_startup,
            "timer_minutes": self.timer_duration // 60,
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
            
        # Validate and clean data after loading
        self.validate_and_clean_data()

    def reload_data(self, _) -> None:
        """Reload data from the JSON file."""
        try:
            self.load_data()
            self.build_categories_menu()
            rumps.notification(
                "Settings",
                "Reload Complete",
                "The data file has been reloaded successfully.",
            )
        except Exception as e:
            rumps.alert(f"Error reloading data file: {e}")

    def save_data(self) -> None:
        """Save data to JSON file."""
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def build_categories_menu(self):
        """Rebuild the 'Categories' submenu based on self.data['categories']."""
        if "Categories" not in self.menu:
            self.menu.insert_after("Statistics", rumps.MenuItem("Categories"))

        categories_item = self.menu["Categories"]
        for key in list(categories_item.keys()):
            del categories_item[key]

        for cat in self.data["categories"].keys():
            cat_item = rumps.MenuItem(cat)
            cat_item.add(rumps.MenuItem("Delete Category", callback=partial(self.delete_category, cat)))
            categories_item.add(cat_item)

    def open_data_location(self, _) -> None:
        """Open the data file location in Finder."""
        os.system(f'open "{self.data_path}"')

    def open_app_support_dir(self, _) -> None:
        """Open the Application Support directory in Finder."""
        os.system(f'open "{self.APP_SUPPORT_DIR}"')

    def update_timer(self, _) -> None:
        """Update the timer display and handle timer completion."""
        self.time_remaining -= 1
        # Safety check to prevent negative time_remaining
        if self.time_remaining < 0:
            self.time_remaining = 0
            
        if self.time_remaining <= 0:
            self.time_remaining = 0
            self.timer.stop()
            self.timer_running = False
            self.timer_paused = False
            self.title = "0:00:00"
            self.save_timer_to_json()
            self.time_remaining = self.timer_duration
            self.update_ui_states()
        else:
            self.title = self.format_time(self.time_remaining)

    def update_stopwatch(self, _) -> None:
        """Update the stopwatch display."""
        self.time_elapsed += 1
        self.title = self.format_time(self.time_elapsed)

    def format_time(self, seconds: int) -> str:
        """Format integer seconds as H:MM:SS."""
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hrs}:{mins:02d}:{secs:02d}"

    def format_time_minutes(self, minutes: float) -> str:
        """Format minutes as H:MM.mm."""
        hrs = int(minutes) // 60
        mins = minutes - (hrs * 60)
        return f"{hrs}:{mins:05.2f}"

    def format_hours_minutes_seconds(self, minutes: float) -> str:
        """Format time in minutes as H:MM:SS."""
        total_seconds = int(round(minutes * 60))
        hrs = total_seconds // 3600
        mins = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hrs}:{mins:02d}:{secs:02d}"

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
            if not (exists login item "Deep Work Timer") then
                make login item at end with properties {{path:"{app_path}", hidden:false}}
            end if
        end tell
        """
        os.system(f"osascript -e '{script}'")

    def remove_from_login_items(self) -> None:
        """Remove this app from the user's login items."""
        script = """
        tell application "System Events"
            delete login item "Deep Work Timer"
        end tell
        """
        os.system(f"osascript -e '{script}'")

    def delete_category(self, category_name, _) -> None:
        """Delete a category by name, after creating a backup."""
        if category_name in self.data["categories"]:
            backup_dir = self.APP_SUPPORT_DIR / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_path = backup_dir / f"data_backup_{timestamp}_{category_name}.json"
            shutil.copy(self.data_path, backup_path)

            del self.data["categories"][category_name]
            self.save_data()
            self.build_categories_menu()

    def add_category(self, _) -> None:
        """Prompt the user to add a new category."""
        name = self.get_text_input("Add Category", "Enter category name:")
        if name and name not in self.data["categories"]:
            self.data["categories"][name] = []
            self.save_data()
            self.build_categories_menu()
        elif name:
            rumps.alert("Category already exists.")

    def add_entry(self, _) -> None:
        """Prompt the user to add a manual time entry."""
        if not self.data["categories"]:
            rumps.alert("No categories available. Please add a category first.")
            return

        category_name = self.select_category(list(self.data["categories"].keys()))
        if not category_name or category_name not in self.data["categories"]:
            return

        date_value, time_minutes = self.get_date_time_input()
        if date_value is None or time_minutes is None:
            return

        entry = {"date": date_value.isoformat(), "time": time_minutes}
        self.data["categories"][category_name].append(entry)
        self.save_data()

    def save_stopwatch_to_json(self):
        """Save stopwatch time to selected category."""
        if not self.data["categories"]:
            rumps.alert("No categories available. Please add a category first.")
            return

        category_name = self.select_category(list(self.data["categories"].keys()))
        if not category_name:
            return

        time_value = round(self.time_elapsed / 60, 2)
        # Validate that time is not negative
        if time_value <= 0:
            rumps.alert("Cannot save zero or negative time. Please start the stopwatch first.")
            return
            
        entry = {"date": datetime.now().isoformat(), "time": time_value}
        self.data["categories"][category_name].append(entry)
        self.save_data()

    def save_timer_to_json(self, elapsed_seconds=None):
        """Save timer time to selected category."""
        if elapsed_seconds is None:
            elapsed_seconds = self.timer_duration - self.time_remaining

        # Validate that elapsed time is not negative
        if elapsed_seconds < 0:
            rumps.alert("Cannot save negative time. Please start the timer first.")
            return

        if not self.data["categories"]:
            rumps.alert("No categories available. Please add a category first.")
            return

        category_name = self.select_category(list(self.data["categories"].keys()))
        if not category_name:
            return

        time_value = round(elapsed_seconds / 60, 2)
        entry = {"date": datetime.now().isoformat(), "time": time_value}
        self.data["categories"][category_name].append(entry)
        self.save_data()

    def show_statistics(self, _) -> None:
        """Show statistics with daily, weekly, and lifetime totals."""
        if not self.data["categories"]:
            rumps.alert("No categories available to show statistics.")
            return

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        per_category_stats = {}
        overall_daily = overall_weekly = overall_lifetime = 0

        for category, entries in self.data["categories"].items():
            daily = weekly = lifetime = 0

            for entry in entries:
                try:
                    entry_date = datetime.fromisoformat(entry["date"]).date()
                    time_spent = entry["time"]
                    lifetime += time_spent

                    if entry_date == today:
                        daily += time_spent
                    if week_ago <= entry_date <= today:
                        weekly += time_spent
                except ValueError:
                    continue

            per_category_stats[category] = {
                "daily": daily,
                "weekly": weekly,
                "lifetime": lifetime,
            }

            overall_daily += daily
            overall_weekly += weekly
            overall_lifetime += lifetime

        stats = "Deep Work Statistics:\n\n"
        
        # Daily statistics - only show categories with time > 0
        stats += f"Daily Total: {self.format_hours_minutes_seconds(overall_daily)}\n"
        for category, stats_dict in per_category_stats.items():
            if stats_dict["daily"] > 0:
                stats += f"  {category}: {self.format_hours_minutes_seconds(stats_dict['daily'])}\n"
        stats += "\n"
        
        # Weekly statistics - only show categories with time > 0
        stats += f"Weekly Total: {self.format_hours_minutes_seconds(overall_weekly)}\n"
        for category, stats_dict in per_category_stats.items():
            if stats_dict["weekly"] > 0:
                stats += f"  {category}: {self.format_hours_minutes_seconds(stats_dict['weekly'])}\n"
        stats += "\n"
        
        # Lifetime statistics - show all categories
        stats += f"Lifetime Total: {self.format_hours_minutes_seconds(overall_lifetime)}\n"
        for category, stats_dict in per_category_stats.items():
            stats += f"  {category}: {self.format_hours_minutes_seconds(stats_dict['lifetime'])}\n"

        rumps.alert(stats)

    def update_ui_states(self):
        """Update the enabled/disabled state of menu items."""
        # Timer controls - disabled if stopwatch is running or paused
        timer_items = {
            "Start Timer": not self.timer_running and not self.stopwatch_running and self.time_elapsed == 0,
            "Pause Timer": self.timer_running and not self.stopwatch_running,
            "Change Timer Duration": not self.timer_running and not self.stopwatch_running and self.time_elapsed == 0,
            "Reset and Save Timer": (self.timer_running or self.timer_paused or self.time_remaining < self.timer_duration) and not self.stopwatch_running
        }
        for item, enabled in timer_items.items():
            self.menu[item].set_callback(self.original_callbacks[item] if enabled else None)

        # Stopwatch controls - disabled if timer is running or paused
        stopwatch_items = {
            "Start Stopwatch": not self.stopwatch_running and not self.timer_running and self.time_remaining == self.timer_duration,
            "Pause Stopwatch": self.stopwatch_running and not self.timer_running,
            "Reset and Save Stopwatch": (self.stopwatch_running or self.stopwatch_paused or self.time_elapsed > 0) and not self.timer_running
        }
        for item, enabled in stopwatch_items.items():
            self.menu[item].set_callback(self.original_callbacks[item] if enabled else None)

    @rumps.clicked("Start Timer")
    def start_resume_timer(self, _):
        """Start or resume the timer."""
        if not self.timer_running:
            self.timer_running = True
            self.timer_paused = False
            self.timer.start()
        self.update_ui_states()

    @rumps.clicked("Pause Timer")
    def pause_timer(self, _):
        """Pause the timer."""
        if self.timer_running:
            self.timer.stop()
            self.timer_running = False
            self.timer_paused = True
        self.update_ui_states()

    @rumps.clicked("Reset and Save Timer")
    def reset_and_save_timer(self, _):
        """Reset and save the timer."""
        self.timer.stop()
        self.timer_running = False
        self.timer_paused = False
        elapsed_seconds = self.timer_duration - self.time_remaining
        self.save_timer_to_json(elapsed_seconds=elapsed_seconds)
        self.time_remaining = self.timer_duration
        self.title = "0:00:00"
        self.update_ui_states()

    @rumps.clicked("Start Stopwatch")
    def start_resume_stopwatch(self, _):
        """Start or resume the stopwatch."""
        if not self.stopwatch_running:
            self.stopwatch_running = True
            self.stopwatch_paused = False
            self.stopwatch.start()
        self.update_ui_states()

    @rumps.clicked("Pause Stopwatch")
    def pause_stopwatch(self, _):
        """Pause the stopwatch."""
        if self.stopwatch_running:
            self.stopwatch.stop()
            self.stopwatch_running = False
            self.stopwatch_paused = True
        self.update_ui_states()

    @rumps.clicked("Reset and Save Stopwatch")
    def reset_and_save_stopwatch(self, _):
        """Reset and save the stopwatch."""
        self.stopwatch.stop()
        self.stopwatch_running = False
        self.stopwatch_paused = False
        self.save_stopwatch_to_json()
        self.time_elapsed = 0
        self.title = "0:00:00"
        self.update_ui_states()

    @rumps.clicked("Change Timer Duration")
    def change_timer_duration(self, _):
        """Change the default timer duration using a slider."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("")
        alert.setInformativeText_("")
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        container_view = NSView.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(300, 60))
        )

        # Create slider
        slider = NSSlider.alloc().initWithFrame_(
            NSRect(NSPoint(0, 30), NSSize(300, 24))
        )
        slider.setMinValue_(30)  # Start from 30 minutes
        slider.setMaxValue_(240)  # 4 hours max
        slider.setIntValue_(self.timer_duration // 60)
        
        # Set up 5-minute increments
        slider.setNumberOfTickMarks_(43)  # (240 - 30) minutes / 5 minutes = 42 tick marks + 1
        slider.setTickMarkPosition_(1)  # Show tick marks below the slider
        slider.setAllowsTickMarkValuesOnly_(True)  # Make it snap to tick marks
        
        # Create label to show current value
        label = NSTextField.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(300, 24))
        )
        label.setStringValue_(f"Current duration: {self.timer_duration // 60} minutes")
        label.setEditable_(False)
        label.setBordered_(False)
        label.setBackgroundColor_(None)
        
        # Create a delegate to handle slider changes
        delegate = SliderDelegate.alloc().init()
        # Store delegate as instance variable to prevent garbage collection
        self._slider_delegate = delegate
        delegate.setLabel_(label)
        slider.setTarget_(delegate)
        slider.setAction_("sliderChanged:")

        container_view.addSubview_(slider)
        container_view.addSubview_(label)
        alert.setAccessoryView_(container_view)

        self._position_alert_window(alert)
        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

        response = alert.runModal()
        if response == NSAlertFirstButtonReturn:
            new_timer_val = int(slider.intValue())
            self.timer_duration = new_timer_val * 60
            self.time_remaining = self.timer_duration
            self.save_settings()
        
        # Clean up the delegate reference
        self._slider_delegate = None

    def get_text_input(self, title: str, message: str) -> str:
        """Prompt the user for text input."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        textfield = NSTextField.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(300, 24))
        )
        alert.setAccessoryView_(textfield)

        self._position_alert_window(alert)
        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        alert.window().setInitialFirstResponder_(textfield)

        response = alert.runModal()
        if response == NSAlertFirstButtonReturn:
            return textfield.stringValue().strip()
        return None

    def get_date_time_input(self):
        """Prompt the user for a date/time and a time duration in minutes."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Manual Entry")
        alert.setInformativeText_("Enter a date/time (MM/DD/YY HH:MM) and time in minutes:")
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        container_view = NSView.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(300, 60))
        )

        datetime_field = NSTextField.alloc().initWithFrame_(
            NSRect(NSPoint(0, 30), NSSize(300, 24))
        )
        datetime_field.setStringValue_(datetime.now().strftime("%m/%d/%y %H:%M"))

        time_field = NSTextField.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(300, 24))
        )
        time_field.setPlaceholderString_("Time in minutes")

        container_view.addSubview_(time_field)
        container_view.addSubview_(datetime_field)
        alert.setAccessoryView_(container_view)

        self._position_alert_window(alert)
        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        alert.window().setInitialFirstResponder_(datetime_field)

        response = alert.runModal()
        if response == NSAlertFirstButtonReturn:
            datetime_str = datetime_field.stringValue().strip()
            time_str = time_field.stringValue().strip()

            try:
                date_value = datetime.strptime(datetime_str, "%m/%d/%y %H:%M")
            except ValueError:
                rumps.alert("Invalid date/time format. Please enter in MM/DD/YY HH:MM format.")
                return None, None

            try:
                time_minutes = float(time_str)
                if time_minutes <= 0:
                    rumps.alert("Invalid input. Please enter a positive number for time in minutes.")
                    return None, None
                # Additional validation: reasonable time limit (24 hours = 1440 minutes)
                if time_minutes > 1440:
                    rumps.alert("Invalid input. Please enter a time less than 24 hours (1440 minutes).")
                    return None, None
                return date_value, time_minutes
            except ValueError:
                rumps.alert("Invalid time in minutes. Please enter a numeric value.")
                return None, None

        return None, None

    def select_category(self, categories: list) -> str:
        """Display a dialog with a combo box to select a category."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Select Category")
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        combobox = NSComboBox.alloc().initWithFrame_(
            NSRect(NSPoint(0, 0), NSSize(300, 24))
        )
        combobox.addItemsWithObjectValues_(categories)
        combobox.selectItemAtIndex_(0)
        alert.setAccessoryView_(combobox)

        self._position_alert_window(alert)
        alert.window().makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        alert.window().setInitialFirstResponder_(combobox)

        response = alert.runModal()
        if response == NSAlertFirstButtonReturn:
            return combobox.stringValue()
        return None

    def _position_alert_window(self, alert):
        """Position the alert window in the top-right corner of the screen."""
        alert_window = alert.window()
        screen_frame = NSScreen.mainScreen().frame()
        alert_width = 600
        alert_height = 200

        alert_x = screen_frame.size.width - alert_width
        alert_y = screen_frame.size.height - alert_height
        alert_window.setFrame_display_animate_(
            NSRect(NSPoint(alert_x, alert_y), NSSize(alert_width, alert_height)),
            True,
            False,
        )

    def validate_and_clean_data(self) -> None:
        """Validate and clean up data entries, removing any negative time values."""
        cleaned = False
        for category in list(self.data["categories"].keys()):
            # Filter out entries with negative or zero time
            original_count = len(self.data["categories"][category])
            self.data["categories"][category] = [
                entry for entry in self.data["categories"][category]
                if isinstance(entry.get("time"), (int, float)) and entry["time"] > 0
            ]
            new_count = len(self.data["categories"][category])
            if new_count < original_count:
                cleaned = True
                print(f"Cleaned {original_count - new_count} invalid entries from category '{category}'")
        
        if cleaned:
            self.save_data()
            print("Data file has been cleaned of invalid entries.")

    # ------------------------------------------------------------------ #
    # one-shot timer: runs once, then stops itself
    def _late_init(self, t):
        t.stop()                  # important – we only need it once
        self.update_ui_states()   # now it *sticks*


if __name__ == "__main__":
    app = StopwatchApp()
    app.run()
