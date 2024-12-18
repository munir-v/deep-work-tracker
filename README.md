# Deep Work Tracker

A simple menu bar app for Mac that helps you track your deep work blocks.

![Deep Work Timer](<screenshots/Deep Work Timer example.png>)

Features
--------
- Allows you to track how much work you do and save the results to custom categories.
- Provides statistics with daily, weekly, and total time spent in each category.

<img src="screenshots/Deep Work Timer statistics.png" alt="Example Stats" style="width:75%; height:auto;">



Installation
------------
As a python script:
1. Clone or download the repository to your local machine.
2. Install the necessary Python libraries using pip:

    ```
    pip install -r requirements.txt
    ```

3. Run the `app.py` script:

    ```
    python app.py
    ```

As a standalone application:
1. Install Py2App
2. Build the app using the preconfigured setup.py file

    ```
    python setup.py py2app
    ```
3. Launch application by double-clicking app or open via Terminal.
4. (Optional) Move application to application folder and enable the "Start at Startup" to launch on system startup.