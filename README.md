# RGB Matrix Ticker

This project drives two chained 64x32 RGB LED matrix panels (total size
128x32) using a Raspberry Pi.  It displays the current date/time along
with configurable stock and cryptocurrency ticker symbols and headlines
from an RSS news feed.

A small Flask web application provides a password protected web
interface (default ``admin:admin``) to manage the list of symbols,
configure the news feed, adjust brightness and change the password.

## Usage

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python app.py
   ```
3. Open `http://<raspberrypi>:8000/` and log in with the default
   credentials.  From there you can add/remove tickers, set the RSS feed,
   adjust brightness and change the password.

The display loop will cycle through the current date/time, the ticker
values and the latest headlines.

