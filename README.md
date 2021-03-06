# Map'A'Droid
![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)

![MAD-Banner](static/banner_small_web.png)

Map'A'Droid is a Raid & Pokémon scanner for Pokémon GO, based on Android devices.

## Information
*  [Discord](https://discord.gg/7TT58jU) - For general support
*  [Github Issues](https://github.com/Map-A-Droid/MAD/issues) - For reporting bugs (not for support!)

## Requirements
- Python 3.6
- MySQL database, with RocketMap or Monocle structure
- Rooted Android device
- PogoDroid token (only necessary for MITM Mode), obtainable [via Patreon](https://www.patreon.com/user?u=14159560)

>MAD is compatible with [this Monocle schema](https://github.com/whitewillem/PMSF/blob/master/cleandb.sql) and [this RocketMap fork](https://github.com/cecpk/OSM-Rocketmap). Please use them or change your database accordingly.

## Setup
### Ubuntu/Debian

Install `python 3.6` & `pip3` according to docs for your platform.  

Once Python is installed, ensure that `pip` and `python` is installed correctly by running:
* `python3.6 --version` - should return `3.6.X`
* `pip3 --version` - If it returns a version, it is working.  

Clone this repository:
```bash
git clone https://github.com/Map-A-Droid/MAD.git
```

Make sure you're in the directory of MAD and run:
```bash
pip3 install -r requirements.txt
```
If you want to use OCR to scan raids, run with `requirements_ocr.txt` and install additional packages: `apt-get install tesseract-ocr python-opencv`


## MAD concept
![MAD concept graphic](static/concept.jpg)

**RGC (Remote GPS Controller)** is responsible for receiving the GPS commands from your server, taking screenshots (if OCR is enabled) and managing Pokémon Go on the phone (restarting, detecting if POGO is opened, etc)

**PogoDroid** is the MITM (Man in the middle) App for reading the data from Pokémon Go and send it to your server. If you use the OCR method, you don’t need this app.

## Configuration
Inside the `config` folder, duplicate the `config.ini.example` and rename it to `config.ini`. Then populate it with at least the database and websocket configurations.

### Multiple Devices
In order to map devices to areas, do the same with `mappings_example.json` and rename it to `mappings.json`
Refer to mappings_example.json for examples or run `python3.6 start.py -wm` and open the MADMIN mappings editor (http://localhost:5000).  

### Geofence
Each area *requires* `geofence_included`. A geofence can easily be created with [geo.jesparke.net](http://geo.jasparke.net/)
> A geofence requires a name: `[geofence name]` with `lat, lng` per line, no empty lines at the end of file  

## Phone Setup
#### Rooting
1. Ensure your phone has an unlocked bootloader and is able to support root. [Lineage OS](https://lineageos.org/) is a good place to start for a custom ROM and they have good installation instruction for each device.  
2. Install [Magisk](https://www.xda-developers.com/how-to-install-magisk/) to root the phone via recovery. Repackage the MagiskManager App and add Pokémon Go to Magisk Hide. Make sure to delete the folder `/sdcard/MagiskManager` after repackaging.
>It's necessary to pass the Safetynet check to run Pokémon Go on rooted phones. Check the Safetynet status in the MagiskManager App.

#### Applications
Install [RGC (Remote GPS Controller)](https://github.com/Map-A-Droid/MAD/blob/master/APK/RemoteGpsController.apk) and [PogoDroid](https://www.maddev.de/apk/PogoDroid.apk) (only necessary for MITM mode) on the phone. RGC must be installed as a system app. Best practice is to convert it to a system app with [link2sd](https://play.google.com/store/apps/details?id=com.buak.Link2SD).
Both apps requires an Origin header field that's configured in mappings.json. These Origins need to be unique per running python instance.  
The websocket URI for RGC is `ws://<ip>:<port>` and the POST destination for PogoDroid is `http://<ip>:<port>`.
>The port for RGC is 8080 by default and can changed with `ws_port`.  
>The port for PogoDroid is 8000 by default and can changed with `mitmreceiver_port`.  
>**The IP address is the IP of your server, not your phone!**  


To login into PogoDroid, you need a token. You can obtain a token by clicking on `Get Token` in PogoDroid and sending the command `!settoken <your_token>` to the MAD Discord Bot. This will only work, if you're a [Patreon supporter](https://www.patreon.com/user?u=14159560) and linked your account to Discord.

## Launching MAD
Make sure you're in the directory of MAD and run:
```bash
python3 start.py
```  

Usually you want to append `-wm` and `-os`
as arguments to start madmin (browser based monitoring) and the scanner (`-os`) responsible
for controlling devices and receiving data from Pogodroid (if OCR enabled, also take screenshots).

If you want to run OCR on screenshots, run `-oo` to analyse screenshots

## MADMIN
MADMIN is a web frontend to configure MAD to your needs, see the current position of your devices, fix OCR failures. You can enable it with `with_madmin` in the config file or `-wm` as a command line argument. The default port is 5000. See the config.ini.example for more options.

## Security
RGC and PogoDroid both support wss/HTTPS respectively. Thus you may setup
reverse proxies for MAD. The Auth headers in RGC and Pogodroid both use Basic auth.
Meaning the password/username is not encrypted per default, that's to be done by SSL/TLS (wss, HTTPS).
